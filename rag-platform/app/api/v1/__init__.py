from fastapi import APIRouter

from app.api.v1 import conversations, documents, knowledge_bases, tasks

api_router = APIRouter()
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(tasks.router, tags=["tasks"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
