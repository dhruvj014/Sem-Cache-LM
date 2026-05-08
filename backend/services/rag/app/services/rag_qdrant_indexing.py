"""RAG Qdrant collections + Redis manifests (no durable LlamaIndex disk index)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from shared.config.settings import Settings


def repo_files_fingerprint(
    repo_path: Path,
    *,
    required_exts: list[str],
    exclude_dirs: list[str],
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
) -> str:
    ext_norm: list[str] = []
    for e in required_exts:
        e = e.strip().lower()
        if not e:
            continue
        ext_norm.append(e if e.startswith(".") else f".{e}")
    ext_set = frozenset(ext_norm)
    exclude_lower = {p.strip().lower() for p in exclude_dirs if p.strip()}

    lines: list[str] = []
    if repo_path.is_dir():
        for p in sorted(repo_path.rglob("*")):
            if not p.is_file():
                continue
            if any(part.lower() in exclude_lower for part in p.parts):
                continue
            suf = p.suffix.lower()
            if ext_set and suf not in ext_set:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            rel = p.relative_to(repo_path).as_posix()
            lines.append(f"{rel}|{st.st_size}|{int(st.st_mtime_ns)}")
    payload = "\n".join(lines)
    basis = f"{payload}\n{embedding_model}\n{chunk_size}\n{chunk_overlap}"
    return hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()


def ensure_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        return
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(
            size=vector_size,
            distance=qmodels.Distance.COSINE,
        ),
    )


def drop_collection(client: QdrantClient, name: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        client.delete_collection(collection_name=name)


def collection_point_count(client: QdrantClient, name: str) -> int:
    try:
        return int(client.count(collection_name=name, exact=True).count)
    except Exception:
        return 0


def redis_manifest_key(settings: Settings, collection_name: str) -> str:
    prefix = settings.rag_redis_manifest_prefix.rstrip(":")
    return f"{prefix}:{collection_name}"
