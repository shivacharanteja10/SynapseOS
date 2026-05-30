"""Vector storage abstraction for RAG context."""

from __future__ import annotations

import hashlib
import math
from typing import Any
from uuid import uuid4

from synapseos.core.config import Settings
from synapseos.core.logging import get_logger

logger = get_logger(__name__)


class VectorStoreService:
    """RAG vector store with memory, Qdrant, and Chroma backends."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._documents: list[dict[str, Any]] = []
        self._qdrant: Any | None = None
        self._chroma_collection: Any | None = None

    async def connect(self) -> None:
        """Connect to the configured vector backend."""

        if self.settings.vector_backend == "qdrant":
            await self._connect_qdrant()
        elif self.settings.vector_backend == "chroma":
            await self._connect_chroma()
        else:
            logger.info("vector_store_memory_backend_ready")

    async def add_text(
        self,
        *,
        task_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a text document to the vector store."""

        metadata = {"task_id": task_id, **(metadata or {})}
        embedding = _embed(content, self.settings.embedding_dimensions)
        self._documents.append({"content": content, "metadata": metadata, "embedding": embedding})

        if self._qdrant is not None:
            try:
                from qdrant_client.http.models import PointStruct

                await self._qdrant.upsert(
                    collection_name=self.settings.qdrant_collection,
                    points=[
                        PointStruct(
                            id=str(uuid4()),
                            vector=embedding,
                            payload={"content": content, "metadata": metadata},
                        )
                    ],
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("qdrant_upsert_failed", error=str(exc))

        if self._chroma_collection is not None:
            try:
                self._chroma_collection.add(
                    ids=[str(uuid4())],
                    documents=[content],
                    embeddings=[embedding],
                    metadatas=[metadata],
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("chroma_add_failed", error=str(exc))

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for documents relevant to a query."""

        embedding = _embed(query, self.settings.embedding_dimensions)
        if self._qdrant is not None:
            qdrant_results = await self._search_qdrant(embedding, limit)
            if qdrant_results:
                return qdrant_results
        if self._chroma_collection is not None:
            chroma_results = self._search_chroma(embedding, limit)
            if chroma_results:
                return chroma_results
        return _rank_memory(query, embedding, self._documents, limit)

    async def _connect_qdrant(self) -> None:
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.http.models import Distance, VectorParams

            self._qdrant = AsyncQdrantClient(url=self.settings.qdrant_url)
            collections = await self._qdrant.get_collections()
            collection_names = {item.name for item in collections.collections}
            if self.settings.qdrant_collection not in collection_names:
                await self._qdrant.create_collection(
                    collection_name=self.settings.qdrant_collection,
                    vectors_config=VectorParams(
                        size=self.settings.embedding_dimensions,
                        distance=Distance.COSINE,
                    ),
                )
            logger.info("qdrant_connected", url=self.settings.qdrant_url)
        except Exception as exc:  # pragma: no cover
            self._qdrant = None
            logger.warning("qdrant_unavailable_using_memory_fallback", error=str(exc))

    async def _connect_chroma(self) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=self.settings.chroma_persist_dir)
            self._chroma_collection = client.get_or_create_collection(
                self.settings.qdrant_collection
            )
            logger.info("chroma_connected", persist_dir=self.settings.chroma_persist_dir)
        except Exception as exc:  # pragma: no cover
            self._chroma_collection = None
            logger.warning("chroma_unavailable_using_memory_fallback", error=str(exc))

    async def _search_qdrant(self, embedding: list[float], limit: int) -> list[dict[str, Any]]:
        try:
            results = await self._qdrant.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=embedding,
                limit=limit,
            )
            return [
                {
                    "content": result.payload.get("content", ""),
                    "metadata": result.payload.get("metadata", {}),
                    "score": result.score,
                }
                for result in results
                if result.payload
            ]
        except Exception as exc:  # pragma: no cover
            logger.warning("qdrant_search_failed", error=str(exc))
            return []

    def _search_chroma(self, embedding: list[float], limit: int) -> list[dict[str, Any]]:
        try:
            result = self._chroma_collection.query(
                query_embeddings=[embedding],
                n_results=limit,
            )
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            return [
                {"content": doc, "metadata": metadata, "score": 1.0 - distance}
                for doc, metadata, distance in zip(documents, metadatas, distances, strict=False)
            ]
        except Exception as exc:  # pragma: no cover
            logger.warning("chroma_search_failed", error=str(exc))
            return []


def _embed(text: str, dimensions: int) -> list[float]:
    """Create a deterministic lightweight embedding for local development."""

    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        direction = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += direction
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _rank_memory(
    query: str,
    embedding: list[float],
    documents: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    query_terms = set(query.lower().split())
    scored: list[dict[str, Any]] = []
    for document in documents:
        doc_embedding = document["embedding"]
        cosine = sum(a * b for a, b in zip(embedding, doc_embedding, strict=False))
        term_overlap = len(query_terms.intersection(document["content"].lower().split()))
        score = cosine + term_overlap * 0.03
        scored.append({**document, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return [
        {"content": item["content"], "metadata": item["metadata"], "score": item["score"]}
        for item in scored[:limit]
    ]
