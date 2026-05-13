"""Internal API: export analytics summary + history as JSON or CSV."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from shared.contracts.export import AnalyticsExportEnvelope
from shared.models.schemas import ResponseEnvelope

router = APIRouter()


@router.get("/v1/analytics/export", response_model=ResponseEnvelope[AnalyticsExportEnvelope])
async def internal_analytics_export(
    app_request: Request,
    fmt: str = Query("json", alias="format", pattern="^(json|csv)$"),
):
    analytics = app_request.app.state.analytics_boundary
    summary = (await analytics.summary()).model_dump()
    history = (await analytics.history(200)).model_dump()
    ts = datetime.now(timezone.utc).isoformat()

    if fmt == "json":
        payload = {
            "summary": summary,
            "history": history.get("entries") or [],
            "exported_at": ts,
        }
        return ResponseEnvelope.ok(
            AnalyticsExportEnvelope(kind="json", json_payload=payload, csv_text=None)
        )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["section", "field", "value"])
    for k, v in summary.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            w.writerow(["summary", k, v])
        else:
            w.writerow(["summary", k, str(v)])
    w.writerow([])
    w.writerow(
        ["query", "source", "agent_action", "similarity_score", "latency_ms", "cache_id", "timestamp"]
    )
    for e in history.get("entries") or []:
        if not isinstance(e, dict):
            continue
        w.writerow(
            [
                e.get("query", ""),
                e.get("source", ""),
                e.get("agent_action", ""),
                e.get("similarity_score", ""),
                e.get("latency_ms", ""),
                e.get("cache_id", ""),
                e.get("timestamp", ""),
            ]
        )
    return ResponseEnvelope.ok(
        AnalyticsExportEnvelope(kind="csv", json_payload=None, csv_text=buf.getvalue())
    )
# verified
