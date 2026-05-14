import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from shared.contracts.streams import SCHEMA_VERSION_V1, JobStatus, QuerySubmittedV1
from shared.infra.stream_runtime import xadd_model
from shared.jobs.redis_jobs import decode_job_view, job_create_pending, job_get_all
from shared.models.schemas import (
    QueryJobAccepted,
    QueryJobStatusResponse,
    QueryRequest,
    QueryResponse,
    ResponseEnvelope,
)
from shared.observability.logger import get_logger
from shared.stream_topology import STREAM_QUERY_COMMANDS_V1

logger = get_logger(__name__)
router = APIRouter()


@router.post("/query")
async def submit_query(
    request: QueryRequest,
    raw_request: Request
):
    settings = raw_request.app.state.settings
    try:
        
        job_id = str(uuid.uuid4())
        correlation_id = getattr(raw_request.state, "correlation_id", None) or "unknown"
        redis_infra = raw_request.app.state.redis
        await job_create_pending(
            redis_infra.client,
            job_id=job_id,
            correlation_id=str(correlation_id),
            ttl_seconds=settings.query_job_ttl_seconds,
            query=request.query,
        )
        cmd_id = str(uuid.uuid4())
        evt = QuerySubmittedV1(
            schema_version=SCHEMA_VERSION_V1,
            correlation_id=str(correlation_id),
            job_id=job_id,
            command_id=cmd_id,
            producer="gateway",
            query=request.query,
            session_id=request.session_id,
            similarity_hit_threshold=request.similarity_hit_threshold,
            similarity_gray_zone_low=request.similarity_gray_zone_low,
        )
        await xadd_model(redis_infra.client, STREAM_QUERY_COMMANDS_V1, evt)
        payload = QueryJobAccepted(
            job_id=job_id,
            status_url=f"/api/v1/query/{job_id}",
        )
        return JSONResponse(
            status_code=202,
            content=ResponseEnvelope.ok(payload).model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "query.failed",
            error=str(e),
            error_type=type(e).__name__,
            error_repr=repr(e),
            query_preview=request.query[:80],
            correlation_id=getattr(raw_request.state, "correlation_id", None),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query/{job_id}", response_model=ResponseEnvelope[QueryJobStatusResponse])
async def get_query_job(job_id: str, raw_request: Request):
    raw = await job_get_all(raw_request.app.state.redis.client, job_id)
    if not raw:
        raise HTTPException(status_code=404, detail="job not found or expired")
    view = decode_job_view(raw)
    result = view.get("result")
    if result is not None and isinstance(result, dict):
        try:
            parsed_result = QueryResponse.model_validate(result)
        except Exception:
            parsed_result = None
    else:
        parsed_result = None
    status_str = str(view.get("status", "unknown"))
    body = QueryJobStatusResponse(
        job_id=job_id,
        status=status_str,
        correlation_id=view.get("correlation_id"),
        created_at=view.get("created_at"),
        updated_at=view.get("updated_at"),
        result=parsed_result,
        error=view.get("error") or None,
    )
    if status_str == JobStatus.completed.value and parsed_result is not None:
        user_query = str(view.get("query") or "").strip()
        if not user_query:
            user_query = (parsed_result.matched_query or "").strip()
        analytics = raw_request.app.state.analytics_boundary
        try:
            await analytics.record_query(
                query=user_query or "(query unavailable)",
                source=parsed_result.source,
                agent_action=parsed_result.agent_action,
                similarity_score=parsed_result.similarity_score,
                latency_ms=parsed_result.latency_ms,
                cache_id=parsed_result.cache_id,
                response_text=parsed_result.response,
                job_id=job_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "gateway.analytics_record_failed",
                job_id=job_id,
                error=str(e),
                error_type=type(e).__name__,
            )
    return ResponseEnvelope.ok(body)
