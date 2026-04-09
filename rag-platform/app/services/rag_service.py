from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.orm import Conversation, Message
from app.services.hybrid_retriever import HybridRetriever, RetrievedChunk
from app.services.model_providers import build_chat_model

SYSTEM_PROMPT = """You are a helpful assistant for knowledge-base question answering.
Answer in concise Chinese when the user writes Chinese.
Use only the provided context when it is relevant.
If the context does not contain the answer, say you do not know based on the documents.
Prefer this structure in plain text:
答复:
依据:
引用:
Cite document filenames when appropriate."""


def _format_context(chunks: list[RetrievedChunk]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[{i}] ({c.filename})\n{c.content}")
    return "\n\n".join(parts)


def _sources_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        excerpt = c.content[:280] + ("…" if len(c.content) > 280 else "")
        out.append(
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "filename": c.filename,
                "page": c.page,
                "excerpt": excerpt,
            }
        )
    return out


def _local_fallback_answer(user_text: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return (
            "答复:\n"
            "我暂时没有在当前知识库中检索到足够相关的内容来回答这个问题。\n\n"
            "依据:\n"
            "当前检索结果为空，建议换个问法，或先上传更相关的文档。\n\n"
            "引用:\n"
            "无"
        )

    lines = ["答复:", "我已基于当前知识库检索到相关内容，下面给出最相关的摘要片段。", "", "依据:"]
    for idx, chunk in enumerate(chunks[:3], start=1):
        excerpt = " ".join(chunk.content.split())
        if len(excerpt) > 220:
            excerpt = excerpt[:220].rstrip() + "..."
        lines.append(f"{idx}. {excerpt}")
    lines.extend(["", "引用:"])
    for chunk in chunks[:3]:
        lines.append(f"- {chunk.filename}")
    lines.append("")
    lines.append("备注: 当前返回为本地检索摘要模式；如需更自然的生成式回答，请配置 CHAT_API_KEY / CHAT_BASE_URL / CHAT_MODEL。")
    return "\n".join(lines)


class RAGService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.retriever = HybridRetriever(db, self.settings)

    def _history_messages(self, conv_id: uuid.UUID) -> list:
        rows = (
            self.db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .limit(self.settings.chat_history_max_messages)
            .all()
        )
        msgs: list = []
        for m in rows:
            if m.role == "user":
                msgs.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                msgs.append(AIMessage(content=m.content))
        return msgs

    async def stream_events(
        self,
        conversation_id: uuid.UUID,
        user_text: str,
        hybrid: bool = True,
        top_k: int | None = None,
    ) -> AsyncIterator[dict]:
        conv = self.db.get(Conversation, conversation_id)
        if not conv:
            yield {"type": "error", "message": "conversation_not_found"}
            return

        chunks = self.retriever.retrieve(
            user_text,
            conv.kb_id,
            hybrid=hybrid,
            final_top_k=top_k,
            use_cache=True,
        )
        yield {"type": "sources", "sources": _sources_payload(chunks)}

        context = _format_context(chunks)
        history = self._history_messages(conversation_id)
        llm = build_chat_model(self.settings, streaming=True, temperature=0.2)
        # #region agent log - after build_chat_model
        import sys
        sys.stderr.write(f"[DEBUG-RAG] build_chat_model returned: llm_is_none={llm is None}, settings.chat_enabled={self.settings.chat_enabled}\n")
        sys.stderr.flush()
        # #endregion

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *history,
            HumanMessage(
                content=f"Context from knowledge base:\n{context}\n\nQuestion:\n{user_text}"
            ),
        ]

        user_msg = Message(conversation_id=conversation_id, role="user", content=user_text)
        self.db.add(user_msg)
        self.db.commit()

        if llm is None:
            # #region agent log - fallback branch
            import sys
            sys.stderr.write("[DEBUG-RAG] LLM is None - entering fallback mode\n")
            sys.stderr.flush()
            # #endregion
            assistant_text = _local_fallback_answer(user_text, chunks)
            asst_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_text,
                sources_json=json.dumps(_sources_payload(chunks), ensure_ascii=False),
            )
            self.db.add(asst_msg)
            if not conv.title:
                conv.title = user_text[:80] + ("…" if len(user_text) > 80 else "")
            self.db.commit()
            yield {"type": "delta", "delta": assistant_text}
            yield {"type": "done", "done": True}
            return

        full: list[str] = []
        try:
            # #region agent log - starting LLM
            import sys
            sys.stderr.write(f"[DEBUG-RAG] Starting LLM astream with {len(messages)} messages\n")
            sys.stderr.flush()
            # #endregion
            async for chunk in llm.astream(messages):
                text = chunk.content
                if text:
                    full.append(text)
                    yield {"type": "delta", "delta": text}
        except Exception as e:
            # #region agent log - LLM exception
            import sys, traceback
            sys.stderr.write(f"[DEBUG-RAG] LLM exception: {e}\n")
            sys.stderr.write(f"[DEBUG-RAG] Traceback: {traceback.format_exc()[:500]}\n")
            sys.stderr.flush()
            # #endregion
            assistant_text = _local_fallback_answer(user_text, chunks)
            yield {"type": "delta", "delta": assistant_text}
            full = [assistant_text]

        assistant_text = "".join(full)
        src_json = json.dumps(_sources_payload(chunks), ensure_ascii=False)
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_text,
            sources_json=src_json,
        )
        self.db.add(asst_msg)
        if not conv.title:
            conv.title = user_text[:80] + ("…" if len(user_text) > 80 else "")
        self.db.commit()

        yield {"type": "done", "done": True}

    def answer_sync(
        self,
        conversation_id: uuid.UUID,
        user_text: str,
        hybrid: bool = True,
        top_k: int | None = None,
    ) -> tuple[str, list[dict]]:
        conv = self.db.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("conversation_not_found")

        chunks = self.retriever.retrieve(
            user_text,
            conv.kb_id,
            hybrid=hybrid,
            final_top_k=top_k,
            use_cache=True,
        )
        sources = _sources_payload(chunks)
        context = _format_context(chunks)
        history = self._history_messages(conversation_id)
        llm = build_chat_model(self.settings, streaming=False, temperature=0.2)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *history,
            HumanMessage(
                content=f"Context from knowledge base:\n{context}\n\nQuestion:\n{user_text}"
            ),
        ]
        user_msg = Message(conversation_id=conversation_id, role="user", content=user_text)
        self.db.add(user_msg)
        self.db.commit()

        if llm is None:
            text = _local_fallback_answer(user_text, chunks)
        else:
            try:
                res = llm.invoke(messages)
                text = str(res.content)
            except Exception:
                text = _local_fallback_answer(user_text, chunks)
        src_json = json.dumps(sources, ensure_ascii=False)
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=text,
            sources_json=src_json,
        )
        self.db.add(asst_msg)
        if not conv.title:
            conv.title = user_text[:80] + ("…" if len(user_text) > 80 else "")
        self.db.commit()
        return text, sources
