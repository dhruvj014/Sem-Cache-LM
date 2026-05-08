from pathlib import Path

from services.rag.app.services.rag_qdrant_indexing import repo_files_fingerprint


def test_repo_files_fingerprint_stable(tmp_path: Path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "a.py").write_text("print(1)", encoding="utf-8")
    fp1 = repo_files_fingerprint(
        d,
        required_exts=[".py"],
        exclude_dirs=["__pycache__"],
        embedding_model="m",
        chunk_size=100,
        chunk_overlap=10,
    )
    fp2 = repo_files_fingerprint(
        d,
        required_exts=[".py"],
        exclude_dirs=["__pycache__"],
        embedding_model="m",
        chunk_size=100,
        chunk_overlap=10,
    )
    assert fp1 == fp2
    fp3 = repo_files_fingerprint(
        d,
        required_exts=[".py"],
        exclude_dirs=["__pycache__"],
        embedding_model="other",
        chunk_size=100,
        chunk_overlap=10,
    )
    assert fp1 != fp3
