import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app import __version__
from app.core.config import settings, MeiliEnvironment
from app.rag.api.router import router as chat_router
from app.rag.factory import get_vector_repository

# logging 설정
logging.basicConfig(
    level=logging.INFO,
    format="(%(asctime)s) %(name)s.%(funcName)s:%(lineno)d: [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Meilisearch 설정 (서버 가동 시점에 최초 1회 실행)
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Initializing server setup ...")
        logger.info(f"Meilisearch HTTP address: {settings.MEILI_HTTP_ADDR}")
        logger.info(f"MeilSsearch environment: {settings.MEILI_ENVIRONMENT}")

        # Fastapi 서버와 Meilisearch 운영 환경이 다를 경우 인덱스 초기화 과정 생략
        if settings.ENV != settings.MEILI_ENVIRONMENT:
            logger.info("Skipping Meilisearch index initialization.")

        # Meilisearch가 개발 환경에서 구동 중인 경우에만 테스트용 인덱스에 대한 초기화 수행
        elif settings.MEILI_ENVIRONMENT == MeiliEnvironment.development:
            repo = get_vector_repository()
            if hasattr(repo, "initialize"):
                await repo.initialize(
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


# MAIN
app = FastAPI(
    title="CatchUp RAG Server",
    lifespan=lifespan,
    redirect_slashes=False,
    version=__version__,
)


# Router 등록
app.include_router(chat_router)


# 헬스 체크
@app.get("/")
async def health_check():
    return {"status": "ok", "message": "RAG Server is running."}


# 응답 시간 추출
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time
    logger.info(f"{request.method} {request.url.path} ===> {process_time:.4f}s")

    return response
