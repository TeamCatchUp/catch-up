import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from catchup import __version__
from catchup.components.vector_db.factory import VectorDbProvider, get_vector_db_service
from catchup.configs.config import MeiliEnvironment, settings
from catchup.db.engine import SessionLocal, engine
from catchup.db.models import Base, Company
from catchup.server.state import state
from catchup.server.auth.api import router as auth_router
from catchup.server.admin.api import router as admin_router
from catchup.server.chat.api import router as chat_router
from catchup.server.chat_room.api import router as chatroom_router
from catchup.server.connector.github.auth_api import router as github_auth_router
from catchup.server.connector.github.sync_api import router as github_sync_router
from catchup.utils.scheduler import init_scheduler, shutdown_scheduler
from catchup.utils.redis import init_langgraph_checkpointer
from catchup.server.connector.atlassian.auth_api import (
    router as atlassian_auth_router,
)
from catchup.server.connector.jira.sync_api import router as jira_sync_router
from catchup.server.connector.jira.webhook_api import router as jira_webhook_router
from catchup.server.connector.confluence.sync_api import (
    router as confluence_sync_router,
)
from catchup.server.connector.slack.auth_api import router as slack_auth_router
from catchup.server.connector.slack.sync_api import router as slack_sync_router
from catchup.server.mapping.api import router as github_mapping_csv_router
from catchup.server.onboarding.api import router as onboarding_router
from catchup.server.settings.api import router as settings_router

# logging 설정
log_level = logging.INFO
if settings.LOG_LEVEL == "debug":
    log_level = logging.DEBUG

logging.basicConfig(
    level=log_level,
    format="(%(asctime)s) %(name)s.%(funcName)s:%(lineno)d: [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# Meilisearch 설정 (서버 가동 시점에 최초 1회 실행)
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Initializing server setup ...")
        logger.info(f"Meilisearch HTTP address: {settings.MEILI_HTTP_ADDR}")
        logger.info(f"MeilSsearch environment: {settings.MEILI_ENVIRONMENT}")
        logger.info(f"Log level: {settings.LOG_LEVEL}")

        # Fastapi 서버와 Meilisearch 운영 환경이 다를 경우 인덱스 초기화 과정 생략
        if settings.ENV != settings.MEILI_ENVIRONMENT:
            logger.info("Skipping Meilisearch index initialization.")

        # Meilisearch가 개발 환경에서 구동 중인 경우에만 테스트용 인덱스에 대한 초기화 수행
        elif settings.MEILI_ENVIRONMENT == MeiliEnvironment.development:
            repo = get_vector_db_service(VectorDbProvider.MEILISEARCH)
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
        logger.info(f"Falied to connect to Meilisearch. {e}")

    try:
        logger.info("Creating tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Done creating tables.")

    except Exception as e:
        logger.critical(f"Failed to create DB tables: {e}")
        raise e
    
    try:
        await init_langgraph_checkpointer()
    
    except Exception as e:
        logger.critical(f"Failed to create Redis langgraph checkpointer: {e}")

    #Scheduler 초기화
    try:
        init_scheduler()
        logger.info("APScheduler initiated Successfully !")
    except Exception as e:
        logger.critical(f"Failed to initialize APScheduler : {e}")
    
    try:
        db = SessionLocal()
        company_count = db.query(Company).count()
        if company_count > 0:
            state.is_admin_initiated = True
        db.close()
    except Exception as e:
        logger.critical(f"Failed to check whether admin is initiated: {e}")
    
    yield

    #Scheduler Shutdown
    try:
        shutdown_scheduler()
    except Exception as e:
        logger.error(f"Failed to Shut Down Scheduler")


# MAIN
app = FastAPI(
    title="CatchUp RAG Server",
    lifespan=lifespan,
    redirect_slashes=False,
    version=__version__,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


# Router 등록
app.include_router(chat_router)
app.include_router(chatroom_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(github_auth_router)
app.include_router(github_sync_router)
app.include_router(atlassian_auth_router)
app.include_router(jira_sync_router)
app.include_router(jira_webhook_router)
app.include_router(confluence_sync_router)
app.include_router(slack_auth_router)
app.include_router(slack_sync_router)
app.include_router(github_mapping_csv_router)
app.include_router(onboarding_router)
app.include_router(settings_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500", # Go Live 포트 허용
        "http://catchup_web:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 헬스 체크
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "message": "Catch Up backend is running."}


# 응답 시간 추출
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time
    logger.info(f"{request.method} {request.url.path} ===> {process_time:.4f}s")

    return response
