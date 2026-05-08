from __future__ import annotations

from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from shared.observability.logger import get_logger

logger = get_logger(__name__)


class QdrantInfrastructure:
    """Owns Qdrant connection and collection bootstrap only."""

    def __init__(self, settings: Any):
        self._settings = settings
        self._client: AsyncQdrantClient | None = None

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise RuntimeError("Qdrant client not initialized. Call connect() first.")
        return self._client

    async def connect(self) -> None:
        self._client = AsyncQdrantClient(
            host=self._settings.qdrant_host,
            port=self._settings.qdrant_port,
            prefer_grpc=False,
        )
        await self._ensure_collection()
        logger.info("qdrant.connected", host=self._settings.qdrant_host)

    async def _ensure_collection(self) -> None:
        collection = self._settings.qdrant_collection
        existing = await self._client.get_collections()
        names = {c.name for c in existing.collections}
        if collection in names:
            return
        await self._client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(
                size=self._settings.qdrant_vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )
        logger.info("qdrant.collection_created", collection=collection)

    async def health(self) -> bool:
        try:
            await self._client.get_collections()
            return True
        except Exception as e:
            logger.warning("qdrant.health_failed", error=str(e))
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

