from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.rag.api.router import router as chat_router
from app.rag.dependencies import get_vector_repository


# Meilisearch 설정 (서버 가동 시점에 최초 1회 실행)
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        repo = get_vector_repository()
        if hasattr(repo, "initialize"):
            repo.initialize()
    except Exception as e:
        print(f"Falied to connect to Meilisearch. {e}")

    yield


app = FastAPI(title="CatchUp RAG Server", lifespan=lifespan)

app.include_router(chat_router)


# 헬스 체크
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "RAG Server is running."}
