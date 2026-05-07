from pathlib import Path

from app.main import create_app
from app.services.api_catalog_service import ApiCatalogService


def test_api_catalog_generation_from_openapi(settings, tmp_path: Path):
    settings.rag_catalog_dir = str(tmp_path / "rag_catalog")
    app = create_app()
    service = ApiCatalogService(settings)

    artifacts = service.generate(app)
    assert artifacts.catalog_json_path.exists()
    assert artifacts.catalog_md_path.exists()
    assert artifacts.payload["api_count"] > 0
    assert any(
        api["path"] == "/api/v1/query" and api["method"] == "POST"
        for api in artifacts.payload["apis"]
    )
