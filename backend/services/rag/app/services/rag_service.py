from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse, urlsplit
from urllib.request import Request, urlopen

from shared.config.settings import Settings
from shared.observability.logger import get_logger
from services.rag.app.services.rag_qdrant_indexing import (
    collection_point_count,
    drop_collection,
    ensure_collection,
    redis_manifest_key,
    repo_files_fingerprint,
)

logger = get_logger(__name__)


@dataclass
class RagCitation:
    file_path: str
    score: float
    snippet: str


@dataclass
class RagResult:
    response: str
    citations: list[RagCitation]


class RagService:
    """RAG service backed by LlamaIndex + Ollama.

    Vector persistence:
    - Default: Qdrant (**RAG_QDRANT_***) per-repo collections + Redis manifests under **rag_redis_manifest_prefix**.
    - Legacy: durable ``rag_index_dir`` docstore (``rag_persist_vectors_in_qdrant=false``).

    Repo clones under ``rag_repo_cache_dir`` remain ephemeral working directories.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._query_engines: dict[str, Any] = {}

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def answer(self, query: str) -> RagResult:
        if not self._query_engines:
            raise RuntimeError("RAG query engine not initialized")
        return await asyncio.to_thread(self._answer_sync, query)

    def _initialize_sync(self) -> None:
        if self._settings.rag_persist_vectors_in_qdrant:
            try:
                self._initialize_qdrant_vector_store()
            except ImportError as e:
                logger.error(
                    "rag.qdrant_backend_missing_dependency",
                    error=str(e),
                    hint="pip install llama-index-vector-stores-qdrant",
                )
                raise
        else:
            self._initialize_legacy_local_disk()

    def _qdrant_collection_name(self, repo_key: str) -> str:
        base_raw = (self._settings.rag_qdrant_collection or "rag").strip()
        base = re.sub(r"[^a-zA-Z0-9_-]", "_", base_raw)[:80]
        safe = self._safe_repo_key(repo_key)[:80]
        merged = f"{base}__{safe}"
        merged = re.sub(r"[^a-zA-Z0-9_-]", "_", merged)
        return merged[:200]

    def _initialize_qdrant_vector_store(self) -> None:
        from llama_index.core import (
            Settings as LlamaSettings,
            SimpleDirectoryReader,
            StorageContext,
            VectorStoreIndex,
        )
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.embeddings.ollama import OllamaEmbedding
        from llama_index.llms.ollama import Ollama
        from llama_index.vector_stores.qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient

        import redis as redis_sync

        repo_paths = self._resolve_repo_paths()

        LlamaSettings.llm = Ollama(
            model=self._settings.ollama_llm_model,
            base_url=self._settings.ollama_base_url,
            request_timeout=self._settings.ollama_timeout_seconds,
        )
        LlamaSettings.embed_model = OllamaEmbedding(
            model_name=self._settings.ollama_embedding_model,
            base_url=self._settings.ollama_base_url,
            ollama_additional_kwargs={"mirostat": 0},
        )
        LlamaSettings.node_parser = SentenceSplitter(
            chunk_size=self._settings.rag_chunk_size,
            chunk_overlap=self._settings.rag_chunk_overlap,
        )

        exts = [
            e.strip()
            for e in self._settings.rag_required_exts.split(",")
            if e.strip()
        ]
        exclude = [
            p.strip()
            for p in self._settings.rag_exclude_dirs.split(",")
            if p.strip()
        ]

        qc = QdrantClient(
            host=self._settings.rag_qdrant_host_resolved,
            port=int(self._settings.rag_qdrant_port_resolved),
        )
        rcli = redis_sync.Redis(
            host=self._settings.redis_host,
            port=int(self._settings.redis_port),
            db=int(self._settings.redis_db),
            decode_responses=True,
        )
        vec_dim = int(self._settings.rag_qdrant_vector_size_resolved)

        self._query_engines = {}
        for repo_key, repo_path in repo_paths.items():
            if not repo_path.exists() or not repo_path.is_dir():
                logger.warning(
                    "rag.repo_skipped",
                    repo=repo_key,
                    reason="path_missing_or_not_dir",
                    path=str(repo_path),
                )
                continue

            coll = self._qdrant_collection_name(repo_key)
            fp = repo_files_fingerprint(
                repo_path,
                required_exts=exts,
                exclude_dirs=exclude,
                embedding_model=self._settings.ollama_embedding_model,
                chunk_size=self._settings.rag_chunk_size,
                chunk_overlap=self._settings.rag_chunk_overlap,
            )
            mkey = redis_manifest_key(self._settings, coll)
            manifest: dict[str, Any] = {}
            raw_m = rcli.get(mkey)
            if raw_m:
                try:
                    manifest = json.loads(raw_m)
                except json.JSONDecodeError:
                    manifest = {}

            pts = collection_point_count(qc, coll)
            cache_hit = manifest.get("fingerprint") == fp and pts > 0

            index = None
            if cache_hit:
                try:
                    vs_load = QdrantVectorStore(client=qc, collection_name=coll)
                    st_load = StorageContext.from_defaults(vector_store=vs_load)
                    index = VectorStoreIndex.from_vector_store(
                        vector_store=vs_load,
                        storage_context=st_load,
                    )
                    logger.info(
                        "rag.index_loaded_qdrant",
                        repo=repo_key,
                        collection=coll,
                        points=pts,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "rag.qdrant_reload_failed_will_rebuild",
                        repo=repo_key,
                        collection=coll,
                        error=str(e),
                    )
                    index = None

            if index is None:
                try:
                    reader = SimpleDirectoryReader(
                        input_dir=str(repo_path),
                        recursive=True,
                        required_exts=exts,
                        exclude=exclude,
                        filename_as_id=True,
                    )
                    documents = reader.load_data()
                except ValueError:
                    logger.warning(
                        "rag.repo_skipped",
                        repo=repo_key,
                        reason="no_files_found_or_reader_init_failed",
                        path=str(repo_path),
                    )
                    continue

                if not documents:
                    logger.warning(
                        "rag.repo_skipped",
                        repo=repo_key,
                        reason="no_documents_loaded",
                        path=str(repo_path),
                    )
                    continue

                drop_collection(qc, coll)
                ensure_collection(qc, coll, vec_dim)
                vs_new = QdrantVectorStore(client=qc, collection_name=coll)
                st_new = StorageContext.from_defaults(vector_store=vs_new)
                index = VectorStoreIndex.from_documents(
                    documents,
                    storage_context=st_new,
                    show_progress=True,
                )
                rcli.set(
                    mkey,
                    json.dumps(
                        {
                            "fingerprint": fp,
                            "collection": coll,
                            "repo_key": repo_key,
                            "embedding_model": self._settings.ollama_embedding_model,
                            "chunk_size": self._settings.rag_chunk_size,
                            "chunk_overlap": self._settings.rag_chunk_overlap,
                            "vector_dim": vec_dim,
                        }
                    ),
                )
                logger.info(
                    "rag.index_built_qdrant",
                    repo=repo_key,
                    collection=coll,
                    documents=len(documents),
                )

            self._query_engines[repo_key] = index.as_query_engine(
                similarity_top_k=self._settings.rag_top_k
            )

        if not self._query_engines:
            raise RuntimeError("No RAG indexes available after repository scan/build.")

    def _initialize_legacy_local_disk(self) -> None:
        from llama_index.core import (
            Settings as LlamaSettings,
            SimpleDirectoryReader,
            StorageContext,
            VectorStoreIndex,
            load_index_from_storage,
        )
        from llama_index.core.node_parser import SentenceSplitter
        from llama_index.embeddings.ollama import OllamaEmbedding
        from llama_index.llms.ollama import Ollama

        repo_paths = self._resolve_repo_paths()
        index_dir = Path(self._settings.rag_index_dir).resolve()
        index_dir.mkdir(parents=True, exist_ok=True)

        LlamaSettings.llm = Ollama(
            model=self._settings.ollama_llm_model,
            base_url=self._settings.ollama_base_url,
            request_timeout=self._settings.ollama_timeout_seconds,
        )
        LlamaSettings.embed_model = OllamaEmbedding(
            model_name=self._settings.ollama_embedding_model,
            base_url=self._settings.ollama_base_url,
            ollama_additional_kwargs={"mirostat": 0},
        )
        LlamaSettings.node_parser = SentenceSplitter(
            chunk_size=self._settings.rag_chunk_size,
            chunk_overlap=self._settings.rag_chunk_overlap,
        )

        exts = [
            e.strip()
            for e in self._settings.rag_required_exts.split(",")
            if e.strip()
        ]
        exclude = [
            p.strip()
            for p in self._settings.rag_exclude_dirs.split(",")
            if p.strip()
        ]

        self._query_engines = {}
        for repo_key, repo_path in repo_paths.items():
            if not repo_path.exists() or not repo_path.is_dir():
                logger.warning(
                    "rag.repo_skipped",
                    repo=repo_key,
                    reason="path_missing_or_not_dir",
                    path=str(repo_path),
                )
                continue

            repo_index_dir = index_dir / self._safe_repo_key(repo_key)
            repo_index_dir.mkdir(parents=True, exist_ok=True)
            persisted_marker = repo_index_dir / "docstore.json"
            if persisted_marker.exists():
                storage = StorageContext.from_defaults(persist_dir=str(repo_index_dir))
                index = load_index_from_storage(storage)
                logger.info(
                    "rag.index_loaded",
                    repo=repo_key,
                    persist_dir=str(repo_index_dir),
                )
            else:
                try:
                    reader = SimpleDirectoryReader(
                        input_dir=str(repo_path),
                        recursive=True,
                        required_exts=exts,
                        exclude=exclude,
                        filename_as_id=True,
                    )
                    documents = reader.load_data()
                except ValueError:
                    logger.warning(
                        "rag.repo_skipped",
                        repo=repo_key,
                        reason="no_files_found_or_reader_init_failed",
                        path=str(repo_path),
                    )
                    continue

                if not documents:
                    logger.warning(
                        "rag.repo_skipped",
                        repo=repo_key,
                        reason="no_documents_loaded",
                        path=str(repo_path),
                    )
                    continue
                index = VectorStoreIndex.from_documents(documents, show_progress=True)
                index.storage_context.persist(persist_dir=str(repo_index_dir))
                logger.info(
                    "rag.index_built",
                    repo=repo_key,
                    persist_dir=str(repo_index_dir),
                    documents=len(documents),
                )

            self._query_engines[repo_key] = index.as_query_engine(
                similarity_top_k=self._settings.rag_top_k
            )

        if not self._query_engines:
            raise RuntimeError("No RAG indexes available after repository scan/build.")

    def _remote_repo_cache_dir_name(self, source: str, parsed) -> str:
        """Directory name under ``rag_repo_cache_dir`` for a single HTTPS git clone."""
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            name = parts[-1]
            if name.casefold().endswith(".git"):
                name = name[:-4]
            return self._safe_repo_key(name)
        return "repo"

    def _resolve_repo_paths(self) -> dict[str, Path]:
        source = (self._settings.rag_repo_path or "").strip()
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            if parsed.netloc == "github.com" and self._looks_like_org_or_user_url(parsed):
                repo_paths = self._clone_github_org_repos(source)
                return self._with_catalog_paths(repo_paths)
            cache_dir = Path(self._settings.rag_repo_cache_dir).resolve()
            cache_dir.mkdir(parents=True, exist_ok=True)
            repo_key = self._remote_repo_cache_dir_name(source, parsed)
            target_dir = cache_dir / repo_key
            if not target_dir.exists():
                logger.info("rag.repo_clone_started", repo=source, target=str(target_dir))
                subprocess.run(
                    ["git", "clone", "--depth", "1", source, str(target_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("rag.repo_clone_finished", target=str(target_dir))
            else:
                logger.info("rag.repo_clone_skipped", reason="already_exists")
            return self._with_catalog_paths({repo_key: target_dir})
        local = Path(source).resolve()
        return self._with_catalog_paths({local.name or "local_repo": local})

    def _looks_like_org_or_user_url(self, parsed_url) -> bool:
        parts = [p for p in parsed_url.path.strip("/").split("/") if p]
        return len(parts) == 1

    def _clone_github_org_repos(self, source: str) -> dict[str, Path]:
        owner = source.rstrip("/").split("/")[-1]
        cache_dir = Path(self._settings.rag_repo_cache_dir).resolve()
        org_root = cache_dir / f"{owner}_repos"
        org_root.mkdir(parents=True, exist_ok=True)

        cached_repo_paths: dict[str, Path] = {}
        for child in org_root.iterdir():
            if child.is_dir() and (child / ".git").exists():
                cached_repo_paths[child.name] = child
        if cached_repo_paths:
            logger.info(
                "rag.org_repos_from_cache",
                owner=owner,
                repos=len(cached_repo_paths),
                root=str(org_root),
            )
            return cached_repo_paths

        repos = self._fetch_owner_repositories(owner)

        selected = repos[: self._settings.rag_org_repo_limit]
        logger.info(
            "rag.org_repos_discovered",
            owner=owner,
            discovered=len(repos),
            selected=len(selected),
        )
        for repo in selected:
            repo_name = repo["name"]
            clone_url = repo["clone_url"]
            target_dir = org_root / repo_name
            if target_dir.exists():
                logger.info("rag.repo_clone_skipped", repo=repo_name, reason="already_exists")
                continue
            logger.info("rag.repo_clone_started", repo=repo_name, target=str(target_dir))
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(target_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("rag.repo_clone_finished", repo=repo_name, target=str(target_dir))

        repo_paths: dict[str, Path] = {}
        for child in org_root.iterdir():
            if child.is_dir():
                repo_paths[child.name] = child
        return repo_paths

    def _fetch_owner_repositories(self, owner: str) -> list[dict[str, str]]:
        token = (self._settings.rag_github_token or "").strip()
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = self._fetch_github_repos(owner, headers)

        repos: list[dict[str, str]] = []
        api_named = 0
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            clone_url = item.get("clone_url")
            if not name or not clone_url:
                continue
            api_named += 1
            if not self._settings.rag_org_include_forks and bool(item.get("fork")):
                continue
            repos.append({"name": str(name), "clone_url": str(clone_url)})

        if not repos:
            if api_named == 0:
                raise RuntimeError(
                    f"No repositories discovered for GitHub owner '{owner}'. "
                    "If you meant one repository, use https://github.com/OWNER/REPO "
                    "(two path segments after github.com). "
                    "For an organization or user with only private repositories, set "
                    "RAG_GITHUB_TOKEN. "
                    "Otherwise verify the owner exists and has at least one public repository "
                    "visible without authentication."
                )
            raise RuntimeError(
                f"GitHub owner '{owner}' returned {api_named} repositories from the API but "
                "none remain after excluding forks. Set RAG_ORG_INCLUDE_FORKS=true to "
                "include fork repositories."
            )

        return repos

    def _fetch_github_repos(
        self, owner: str, headers: dict[str, str]
    ) -> list[dict[str, Any]]:
        endpoints = [
            f"https://api.github.com/orgs/{owner}/repos?per_page=100&sort=updated",
            f"https://api.github.com/users/{owner}/repos?per_page=100&sort=updated",
        ]
        merged: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        last_error: str | None = None

        for url in endpoints:
            try:
                batch = self._fetch_paginated_repo_list(url, headers)
            except RuntimeError as exc:
                last_error = str(exc)
                continue
            for item in batch:
                if not isinstance(item, dict):
                    continue
                rid = item.get("id")
                if isinstance(rid, int):
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                merged.append(item)
            if merged:
                return merged

        if last_error:
            raise RuntimeError(
                f"GitHub repository discovery failed for '{owner}'. "
                f"Last error: {last_error}"
            )
        return []

    def _fetch_paginated_repo_list(
        self, first_url: str, headers: dict[str, str]
    ) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        next_url = first_url
        while next_url:
            req = Request(next_url, headers=headers)
            try:
                resp = urlopen(req, timeout=20)
            except HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                try:
                    payload = json.loads(body)
                    if isinstance(payload, dict) and payload.get("message"):
                        raise RuntimeError(
                            f"{payload['message']} (status={e.code}, url={next_url})"
                        )
                except json.JSONDecodeError:
                    pass
                raise RuntimeError(f"HTTP {e.code} (url={next_url})") from e
            with resp:
                body = resp.read().decode("utf-8")
                payload = json.loads(body)
                if isinstance(payload, dict):
                    message = payload.get("message", "unexpected GitHub API payload")
                    raise RuntimeError(f"{message} (url={next_url})")
                if not isinstance(payload, list):
                    raise RuntimeError(f"Unexpected GitHub API response shape (url={next_url})")
                repos.extend(payload)
                next_url = self._extract_next_link(resp.headers.get("Link"))
        return repos

    def _extract_next_link(self, link_header: str | None) -> str | None:
        if not link_header:
            return None
        parts = [p.strip() for p in link_header.split(",") if p.strip()]
        for p in parts:
            if 'rel="next"' not in p:
                continue
            lt = p.find("<")
            gt = p.find(">", lt + 1)
            if lt == -1 or gt == -1:
                continue
            url = p[lt + 1 : gt]
            parsed = urlsplit(url)
            if not parsed.query:
                return url
            _ = parse_qs(parsed.query, keep_blank_values=True)
            return url
        return None

    def _answer_sync(self, query: str) -> RagResult:
        total_start = time.perf_counter()
        best_response = None
        best_score = -1.0
        collected_nodes: list[tuple[str, Any]] = []
        for repo, engine in self._query_engines.items():
            repo_start = time.perf_counter()
            response = engine.query(query)
            nodes = list(getattr(response, "source_nodes", []) or [])
            if nodes:
                repo_best = max(float(n.score or 0.0) for n in nodes)
            else:
                repo_best = 0.0
            if repo_best > best_score:
                best_score = repo_best
                best_response = response
            for n in nodes:
                collected_nodes.append((repo, n))
            logger.info(
                "rag.repo_query_timing",
                repo=repo,
                latency_ms=round((time.perf_counter() - repo_start) * 1000, 2),
                nodes=len(nodes),
                repo_best=repo_best,
            )

        response = best_response
        if response is None:
            return RagResult(response="", citations=[])

        citations: list[RagCitation] = []
        for repo, node in sorted(
            collected_nodes, key=lambda pair: float(pair[1].score or 0.0), reverse=True
        )[: self._settings.rag_top_k]:
            metadata = node.node.metadata or {}
            path = (
                metadata.get("file_path")
                or metadata.get("filename")
                or metadata.get("id")
                or "unknown"
            )
            file_path = str(path)
            if repo == "catalog_docs":
                if "repo_catalog" in file_path:
                    file_path = f"catalog:repo:{file_path}"
                elif "api_catalog" in file_path:
                    file_path = f"catalog:api:{file_path}"
                else:
                    file_path = f"catalog:{file_path}"
            else:
                file_path = f"{repo}:{file_path}"
            snippet = node.node.get_content()[: self._settings.rag_citation_max_chars]
            citations.append(
                RagCitation(
                    file_path=file_path,
                    score=float(node.score or 0.0),
                    snippet=snippet,
                )
            )

        logger.info(
            "rag.answer_timing",
            latency_ms=round((time.perf_counter() - total_start) * 1000, 2),
            repos=len(self._query_engines),
            citations=len(citations),
        )
        return RagResult(response=str(response), citations=citations)

    def _safe_repo_key(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
        return cleaned or "repo"

    def _with_catalog_paths(self, repo_paths: dict[str, Path]) -> dict[str, Path]:
        catalog_dir = Path(self._settings.rag_catalog_dir).resolve()
        if catalog_dir.exists() and catalog_dir.is_dir():
            has_docs = any(catalog_dir.glob("*.md")) or any(catalog_dir.glob("*.json"))
            if has_docs:
                repo_paths["catalog_docs"] = catalog_dir
        return repo_paths
