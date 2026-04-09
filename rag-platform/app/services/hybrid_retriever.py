from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.orm import Chunk
from app.services.cache import cache_get_json, cache_set_json, embedding_cache_key, retrieval_cache_key
from app.services.model_providers import build_embeddings
from app.services.qdrant_store import QdrantStore


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", text.lower()) if t]


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int | None
    content: str
    score: float


def reciprocal_rank_fusion(
    ranked_lists: list[list[uuid.UUID]],
    k: int = 60,
) -> list[uuid.UUID]:
    scores: dict[uuid.UUID, float] = {}
    for ids in ranked_lists:
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


class HybridRetriever:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        qdrant: QdrantStore | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.qdrant = qdrant or (QdrantStore(self.settings) if self.settings.semantic_search_active else None)
        self.embeddings = build_embeddings(self.settings)

    def _semantic_rank(self, query: str, kb_id: uuid.UUID, k: int) -> list[uuid.UUID]:
        if self.embeddings is None or self.qdrant is None:
            return []
        ek = embedding_cache_key(query)
        cached = cache_get_json(ek)
        if isinstance(cached, list) and cached and isinstance(cached[0], (int, float)):
            vec = [float(x) for x in cached]
        else:
            try:
                vec = self.embeddings.embed_query(query)
                cache_set_json(ek, vec, 86400)
            except Exception:
                return []
        try:
            hits = self.qdrant.search(vec, kb_id, limit=k)
        except Exception:
            return []
        out: list[uuid.UUID] = []
        for h in hits:
            payload = h.payload or {}
            cid = payload.get("chunk_id")
            if cid:
                out.append(uuid.UUID(str(cid)))
        return out

    def _keyword_rank(self, query: str, kb_id: uuid.UUID, k: int) -> list[uuid.UUID]:
        rows = self.db.query(Chunk).filter(Chunk.kb_id == kb_id).all()
        if not rows:
            return []
        corpus = [c.content for c in rows]
        ids = [c.id for c in rows]
        tokenized = [_tokenize(c) for c in corpus]
        if not any(tokenized):
            return []
        bm25 = BM25Okapi(tokenized)
        q = _tokenize(query)
        if not q:
            return []
        scores = bm25.get_scores(q)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [ids[i] for i in ranked[:k]]

    def retrieve(
        self,
        query: str,
        kb_id: uuid.UUID,
        hybrid: bool = True,
        final_top_k: int | None = None,
        use_cache: bool = True,
    ) -> list[RetrievedChunk]:
        fk = final_top_k or self.settings.final_top_k
        sk = self.settings.semantic_k
        kk = self.settings.keyword_k

        if use_cache:
            ck = retrieval_cache_key(kb_id, query, hybrid, fk)
            cached = cache_get_json(ck)
            if cached and isinstance(cached, list):
                ids = [uuid.UUID(x) for x in cached]
                return self._load_chunks_ordered(ids, fk)

        if hybrid:
            sem = self._semantic_rank(query, kb_id, sk)
            keyw = self._keyword_rank(query, kb_id, kk)
            merged = reciprocal_rank_fusion([sem, keyw])
            top_ids = merged[:fk]
        else:
            top_ids = self._semantic_rank(query, kb_id, fk) or self._keyword_rank(query, kb_id, fk)

        if use_cache and top_ids:
            cache_set_json(retrieval_cache_key(kb_id, query, hybrid, fk), [str(i) for i in top_ids], 120)

        return self._load_chunks_ordered(top_ids, fk)

    def _load_chunks_ordered(self, ids: list[uuid.UUID], limit: int) -> list[RetrievedChunk]:
        if not ids:
            return []
        rows = self.db.query(Chunk).filter(Chunk.id.in_(ids)).all()
        by_id = {r.id: r for r in rows}
        out: list[RetrievedChunk] = []
        for cid in ids:
            if len(out) >= limit:
                break
            row = by_id.get(cid)
            if not row:
                continue
            doc = row.document
            out.append(
                RetrievedChunk(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    filename=doc.filename if doc else "",
                    page=row.page,
                    content=row.content,
                    score=0.0,
                )
            )
        return out
