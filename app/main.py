import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.rag.api.router import router as chat_router
from app.rag.factory import get_vector_repository

# logging 설정
logging.basicConfig(
    level=logging.INFO,
    format="(%(asctime)s) %(name)s: [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# Meilisearch 설정 (서버 가동 시점에 최초 1회 실행)
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        print("Initializing server setup ...")
        repo = get_vector_repository()
        if hasattr(repo, "initialize"):
            repo.initialize(
                [
                    settings.MEILI_GITHUB_CODEBASE_INDEX,
                    settings.MEILI_GITHUB_ISSUES_INDEX,
                    settings.MEILI_GITHUB_PRS_INDEX,
                ]
            )
        print("Successfully initilized server setup.")
    except Exception as e:
        print(f"Falied to connect to Meilisearch. {e}")

    yield


app = FastAPI(title="CatchUp RAG Server", lifespan=lifespan)

app.include_router(chat_router)


# 헬스 체크
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "RAG Server is running."}
