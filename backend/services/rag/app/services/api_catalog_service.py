from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute

from shared.config.settings import Settings
from shared.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ApiCatalogArtifacts:
    catalog_json_path: Path
    catalog_md_path: Path
    payload: dict


class ApiCatalogService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def generate(self, app: FastAPI) -> ApiCatalogArtifacts:
        catalog_dir = Path(self._settings.rag_catalog_dir).resolve()
        catalog_dir.mkdir(parents=True, exist_ok=True)
        openapi = app.openapi()
        op_to_module = self._route_module_map(app)

        apis: list[dict] = []
        for path, methods in sorted(openapi.get("paths", {}).items()):
            if not isinstance(methods, dict):
                continue
            for method, op in methods.items():
                if not isinstance(op, dict):
                    continue
                op_id = op.get("operationId", "")
                apis.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "summary": op.get("summary") or "",
                        "description": op.get("description") or "",
                        "tags": op.get("tags") or [],
                        "operation_id": op_id,
                        "module": op_to_module.get((path, method.upper()), ""),
                    }
                )

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "api_count": len(apis),
            "apis": apis,
        }
        json_path = catalog_dir / "api_catalog.json"
        md_path = catalog_dir / "api_catalog.md"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(self._build_markdown(payload), encoding="utf-8")
        logger.info(
            "catalog.api.generated",
            api_count=len(apis),
            json_path=str(json_path),
            md_path=str(md_path),
        )
        return ApiCatalogArtifacts(json_path, md_path, payload)

    def _route_module_map(self, app: FastAPI) -> dict[tuple[str, str], str]:
        mapping: dict[tuple[str, str], str] = {}
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            module = getattr(route.endpoint, "__module__", "")
            for method in route.methods or []:
                if method in {"HEAD", "OPTIONS"}:
                    continue
                mapping[(route.path, method.upper())] = module
        return mapping

    def _build_markdown(self, payload: dict) -> str:
        lines = [
            "# API Catalog",
            "",
            f"Generated at: {payload['generated_at']}",
            f"API count: {payload['api_count']}",
            "",
        ]
        for api in payload["apis"]:
            lines.extend(
                [
                    f"## {api['method']} {api['path']}",
                    f"- Summary: {api['summary'] or 'N/A'}",
                    f"- Description: {api['description'] or 'N/A'}",
                    f"- Tags: {', '.join(api['tags']) if api['tags'] else 'N/A'}",
                    f"- Operation ID: {api['operation_id'] or 'N/A'}",
                    f"- Module: {api['module'] or 'N/A'}",
                    "",
                ]
            )
        return "\n".join(lines).strip() + "\n"
