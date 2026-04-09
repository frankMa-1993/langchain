from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import Settings, get_settings


@lru_cache(maxsize=8)
def _local_qdrant_client(storage_dir: str) -> QdrantClient:
    path = Path(storage_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


class QdrantStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = self._build_client(self.settings.qdrant_url)
        self.collection = self.settings.qdrant_collection

    def _build_client(self, location: str) -> QdrantClient:
        target = (location or "").strip()
        if target.startswith(("http://", "https://")):
            return QdrantClient(url=target, prefer_grpc=False)
        if target == ":memory:":
            return QdrantClient(location=":memory:")
        return _local_qdrant_client(target or ".qdrant")

    def ensure_collection(self, vector_size: int) -> None:
        cols = self.client.get_collections().collections
        names = {c.name for c in cols}
        if self.collection in names:
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
        )

    def upsert_points(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        points = [
            qm.PointStruct(id=pid, vector=vec, payload=pay)
            for pid, vec, pay in zip(ids, vectors, payloads, strict=True)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(
        self,
        vector: list[float],
        kb_id: uuid.UUID,
        limit: int,
        document_id: uuid.UUID | None = None,
    ) -> list[qm.ScoredPoint]:
        must: list[qm.Condition] = [
            qm.FieldCondition(key="kb_id", match=qm.MatchValue(value=str(kb_id))),
        ]
        if document_id:
            must.append(
                qm.FieldCondition(key="document_id", match=qm.MatchValue(value=str(document_id))),
            )
        flt = qm.Filter(must=must)
        res = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
        return res

    def delete_by_document(self, document_id: uuid.UUID) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id",
                            match=qm.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )

    def delete_by_kb(self, kb_id: uuid.UUID) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="kb_id",
                            match=qm.MatchValue(value=str(kb_id)),
                        )
                    ]
                )
            ),
        )
