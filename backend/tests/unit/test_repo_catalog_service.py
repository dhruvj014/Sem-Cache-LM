from pathlib import Path

from app.services.repo_catalog_service import RepoCatalogService


def test_repo_catalog_generation_writes_files(settings, tmp_path: Path):
    cache_dir = tmp_path / "rag_repo_cache"
    repo_dir = cache_dir / "demo-repo"
    git_dir = repo_dir / ".git"
    git_dir.mkdir(parents=True)
    (repo_dir / "README.md").write_text("# Demo\n\nSimple demo repository.", encoding="utf-8")
    (repo_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")

    settings.rag_repo_cache_dir = str(cache_dir)
    settings.rag_catalog_dir = str(tmp_path / "rag_catalog")
    service = RepoCatalogService(settings)

    artifacts = service.generate()
    assert artifacts.catalog_json_path.exists()
    assert artifacts.catalog_md_path.exists()
    assert artifacts.payload["repo_count"] == 1
    assert artifacts.payload["repos"][0]["name"] == "demo-repo"
