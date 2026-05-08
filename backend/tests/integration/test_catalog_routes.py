import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.rag.app.api.catalog import router
from services.rag.app.dependencies import (
    get_api_catalog_service,
    get_catalog_cache_service,
    get_repo_catalog_service,
)


@dataclass
class _Artifacts:
    catalog_json_path: Path
    catalog_md_path: Path
    payload: dict


class _FakeCache:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get_cached_catalog(self, name: str) -> dict:
        return {
            "content": self.data.get(name),
            "meta": self.data.get(f"{name}:meta"),
        }

    async def sync_files(self, paths: list[Path]) -> dict:
        for p in paths:
            self.data[p.name] = p.read_text(encoding="utf-8")
            self.data[f"{p.name}:meta"] = json.dumps({"path": str(p)})
        return {"synced": len(paths), "skipped": 0}


class _FakeRepoCatalog:
    def __init__(self, tmp_path: Path):
        self._tmp = tmp_path

    def generate(self):
        p = self._tmp / "repo_catalog.json"
        md = self._tmp / "repo_catalog.md"
        payload = {"repo_count": 1, "repos": [{"name": "demo"}]}
        p.write_text(json.dumps(payload), encoding="utf-8")
        md.write_text("# repos", encoding="utf-8")
        return _Artifacts(p, md, payload)


class _FakeApiCatalog:
    def __init__(self, tmp_path: Path):
        self._tmp = tmp_path

    def generate(self, app):
        p = self._tmp / "api_catalog.json"
        md = self._tmp / "api_catalog.md"
        payload = {"api_count": 1, "apis": [{"path": "/x", "method": "GET"}]}
        p.write_text(json.dumps(payload), encoding="utf-8")
        md.write_text("# apis", encoding="utf-8")
        return _Artifacts(p, md, payload)


def test_catalog_routes_read_and_refresh(tmp_path: Path):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    fake_cache = _FakeCache()
    fake_repo = _FakeRepoCatalog(tmp_path)
    fake_api = _FakeApiCatalog(tmp_path)
    app.dependency_overrides[get_catalog_cache_service] = lambda: fake_cache
    app.dependency_overrides[get_repo_catalog_service] = lambda: fake_repo
    app.dependency_overrides[get_api_catalog_service] = lambda: fake_api

    client = TestClient(app)

    refresh = client.post("/api/v1/catalog/refresh")
    assert refresh.status_code == 200
    body = refresh.json()["data"]
    assert body["repo_count"] == 1
    assert body["api_count"] == 1

    repos = client.get("/api/v1/catalog/repos")
    assert repos.status_code == 200
    assert repos.json()["data"]["content"]["repo_count"] == 1

    apis = client.get("/api/v1/catalog/apis")
    assert apis.status_code == 200
    assert apis.json()["data"]["content"]["api_count"] == 1
