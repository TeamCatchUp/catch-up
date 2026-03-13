import logging
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from catchup.audit.enums import SystemEventAction
from catchup.audit.system import system_event
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal, engine
from catchup.db.global_state import has_admin_ever_onboarded, has_csv_file_ever_been_uploaded
from catchup.db.models import Base
from catchup.events.enums import EventTopic
from catchup.observability.logging import configure_logging
from catchup.observability.logging.s3_uploader import audit_log_uploader_task, graceful_shutdown
from catchup.server.admin.api import router as admin_router
from catchup.server.auth.api import router as auth_router
from catchup.server.chat.api import router as chat_router
from catchup.server.chat_room.api import router as chatroom_router
from catchup.server.connector.atlassian.auth_api import (
    router as atlassian_auth_router,
)
from catchup.server.connector.github.auth_api import router as github_auth_router
from catchup.server.connector.github.webhook_api import router as github_webhook_router
from catchup.server.connector.jira.webhook_api import router as jira_webhook_router
from catchup.server.connector.slack.auth_api import router as slack_auth_router
from catchup.server.connector.slack.webhook_api import router as slack_webhook_router
from catchup.server.mapping.api import router as github_mapping_csv_router
from catchup.server.middleware.request_context import request_context_middleware
from catchup.server.onboarding.api import router as onboarding_router
from catchup.server.settings.api import router as settings_router
from catchup.server.sync.api import router as sync_runtime_router
from catchup.server.state import state
from catchup.worker.worker_event_processor import run_forever as run_sync_worker
from catchup.utils.redis import get_redis_client
from catchup.utils.scheduler import init_scheduler, shutdown_scheduler
from catchup.utils.client import _shared_client
from catchup.rag.checkpoint import close_langgraph_checkpointer, init_langgraph_checkpointer
from catchup.events.bus import bus
from catchup.audit.handlers import audit_event_handler


debug_mode = settings.ENV == "development" or settings.DEBUGGER_ENABLED

if debug_mode:
    import debugpy
    debugpy.listen(("0.0.0.0", settings.DEBUGGER_PORT))
    # debugpy.wait_for_client()

configure_logging()
logger = logging.getLogger(__name__)

if debug_mode:
    logger.info(f"debugpy_attachment_success: port={settings.DEBUGGER_PORT}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    logger.info("Log level: %s", settings.LOG_LEVEL)
    
    sync_worker_stop_event: asyncio.Event | None = None
    sync_worker_task: asyncio.Task | None = None
    uploader_task: asyncio.Task | None = None  # S3 감사로그 업로드

    if settings.LOG_AUDIT_FILE_ENABLED:
        logger.info(
            "audit_file_rotation_config | when=%s interval=%s backupCount=%s",
            settings.LOG_AUDIT_ROTATION_WHEN,
            settings.LOG_AUDIT_ROTATION_INTERVAL,
            settings.LOG_AUDIT_BACKUP_COUNT,
        )

    if settings.AWS_S3_AUDIT_ENABLED:
        logger.info("[AUDIT][AWS_S3] Starting audit log uploader task to S3")
        uploader_task = asyncio.create_task(audit_log_uploader_task())

    try:
        db_init_started_at = time.perf_counter()

        # 1) 메타데이터 기준 테이블 목록 수집
        metadata_table_names = sorted(Base.metadata.tables.keys())
        system_event(
            action=SystemEventAction.STARTUP_DB_INIT,
            result="start",
            metadata={
                "message": "starting_db_initialization",
                "metadata_table_count": len(metadata_table_names),
            },
        )
        logger.debug(
            "[APP][STARTUP][DB][INIT] Metadata tables loaded: count=%s, tables=%s",
            len(metadata_table_names),
            metadata_table_names,
        )

        # 2) create_all 이전 DB 상태 확인
        with engine.connect() as connection:
            db_inspector_before = inspect(connection)
            db_table_names_before = sorted(db_inspector_before.get_table_names())

        missing_tables_before = sorted(
            set(metadata_table_names) - set(db_table_names_before)
        )
        logger.debug(
            "[APP][STARTUP][DB][INIT] DB tables before create_all: count=%s, tables=%s",
            len(db_table_names_before),
            db_table_names_before,
        )
        logger.debug(
            "[APP][STARTUP][DB][INIT] Missing tables before create_all: count=%s, tables=%s",
            len(missing_tables_before),
            missing_tables_before,
        )

        # 3) SQLAlchemy create_all 실행
        create_all_started_at = time.perf_counter()
        Base.metadata.create_all(bind=engine)
        create_all_elapsed_ms = (time.perf_counter() - create_all_started_at) * 1000
        logger.debug(
            "[APP][STARTUP][DB][INIT] create_all completed: elapsed_ms=%.2f",
            create_all_elapsed_ms,
        )

        # 4) create_all 이후 DB 상태 확인 및 스키마 드리프트 탐지
        with engine.connect() as connection:
            db_inspector_after = inspect(connection)
            db_table_names_after = sorted(db_inspector_after.get_table_names())

            missing_columns_by_table: dict[str, list[str]] = {}
            for table_name in metadata_table_names:
                if table_name not in db_table_names_after:
                    continue

                model_columns = sorted(Base.metadata.tables[table_name].c.keys())
                db_columns = sorted(
                    column["name"] for column in db_inspector_after.get_columns(table_name)
                )
                missing_columns = sorted(set(model_columns) - set(db_columns))
                if missing_columns:
                    missing_columns_by_table[table_name] = missing_columns

        created_tables = sorted(set(db_table_names_after) - set(db_table_names_before))
        missing_tables_after = sorted(set(metadata_table_names) - set(db_table_names_after))

        logger.debug(
            "[APP][STARTUP][DB][INIT] DB tables after create_all: count=%s, tables=%s",
            len(db_table_names_after),
            db_table_names_after,
        )
        logger.debug(
            "[APP][STARTUP][DB][INIT] Created tables in this startup: count=%s, tables=%s",
            len(created_tables),
            created_tables,
        )

        if missing_tables_after:
            system_event(
                action=SystemEventAction.STARTUP_DB_INIT,
                result="partial_failure",
                metadata={
                    "message": "missing_tables_after_create_all",
                    "missing_tables_count": len(missing_tables_after),
                    "missing_tables": missing_tables_after,
                },
            )

        if missing_columns_by_table:
            for table_name, missing_columns in missing_columns_by_table.items():
                system_event(
                    action=SystemEventAction.STARTUP_DB_SCHEMA_DRIFT,
                    result="partial_failure",
                    metadata={
                        "table_name": table_name,
                        "missing_columns": missing_columns,
                    },
                )
        else:
            logger.debug(
                "[APP][STARTUP][DB][SCHEMA_DRIFT] No missing DB columns detected"
            )

        db_init_elapsed_ms = (time.perf_counter() - db_init_started_at) * 1000
        system_event(
            action=SystemEventAction.STARTUP_DB_INIT,
            result="success",
            metadata={
                "elapsed_ms": round(db_init_elapsed_ms, 2),
                "metadata_tables": len(metadata_table_names),
                "db_tables_before": len(db_table_names_before),
                "db_tables_after": len(db_table_names_after),
            },
        )

    except Exception as e:
        system_event(
            action=SystemEventAction.STARTUP_DB_INIT,
            result="failure",
            level="error",
            metadata={"error": str(e)},
        )
        raise

    # Langgraph Checkpoint INIT
    try:
        await init_langgraph_checkpointer()
        system_event(
            action=SystemEventAction.STARTUP_CHECKPOINTER_INIT,
            result="success",
        )
    except Exception as e:
        system_event(
            action=SystemEventAction.STARTUP_CHECKPOINTER_INIT,
            result="failure",
            level="error",
            metadata={"error": str(e)},
        )

    # Scheduler 초기화
    try:
        init_scheduler()
        system_event(
            action=SystemEventAction.STARTUP_SCHEDULER_INIT,
            result="success",
        )
    except Exception as e:
        system_event(
            action=SystemEventAction.STARTUP_SCHEDULER_INIT,
            result="failure",
            level="error",
            metadata={"error": str(e)},
        )

    try:
        await get_redis_client()
        system_event(
            action=SystemEventAction.STARTUP_REDIS_INIT,
            result="success",
        )
    except Exception as e:
        system_event(
            action=SystemEventAction.STARTUP_REDIS_INIT,
            result="failure",
            level="error",
            metadata={"error": str(e)},
        )
        raise e

    if settings.SYNC_WORKER_AUTOSTART:
        sync_worker_stop_event = asyncio.Event()
        sync_worker_task = asyncio.create_task(
            run_sync_worker(sync_worker_stop_event)
        )
        logger.info("[SYNC][WORKER] In-process worker started")
        
    try:
        with SessionLocal() as db:
            # 어드민 온보딩 여부 테스트
            state.is_admin_initiated = has_admin_ever_onboarded(db)
            logger.info(f"Admin onboarding completed: {state.is_admin_initiated}")       
            # 어드민 CSV 파일 최초 업로드 여부
            state.has_ever_uploaded_user_list_export = has_csv_file_ever_been_uploaded(db)
            logger.info(f"User list CSV uploaded before: {state.has_ever_uploaded_user_list_export}")
            
            
    except Exception as e:
        logger.critical(
            "Failed to check whether admin is initiated: %s",
            e,
        )
        
    yield
    
    # 서버 종료 전 감사로그 파일 S3 업로드
    if uploader_task:
        # 백그라운드 작업 취소
        uploader_task.cancel()
        try:
            await uploader_task
        except asyncio.CancelledError:
            pass
        
        try:
            await graceful_shutdown()
            logger.info("audit_file_flush_success (graceful shutdown)")
        except Exception as e:
            logger.critical("audit_file_flush_failed", exc_info=True)

    if sync_worker_stop_event is not None:
        sync_worker_stop_event.set()

    if sync_worker_task is not None:
        try:
            await sync_worker_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "[SYNC][WORKER] Worker shutdown failed: %s", e, exc_info=True
            )

    # Scheduler Shutdown
    try:
        shutdown_scheduler()
        system_event(
            action=SystemEventAction.SHUTDOWN_SCHEDULER,
            result="success",
        )
    except Exception as e:
        system_event(
            action=SystemEventAction.SHUTDOWN_SCHEDULER,
            result="failure",
            level="error",
            metadata={"error": str(e)},
        )

    try:
        await close_langgraph_checkpointer()
        system_event(
            action=SystemEventAction.SHUTDOWN_CHECKPOINTER,
            result="success",
        )
    except Exception as e:
        system_event(
            action=SystemEventAction.SHUTDOWN_CHECKPOINTER,
            result="failure",
            level="error",
            metadata={"error": str(e)},
        )
        
    try:
        await _shared_client.aclose()
    except Exception as e:
        logger.error(
            "Global shared async client shutdown failed: %s", 
            e,
            exc_info=True
        )

# MAIN
app = FastAPI(
    title="CatchUp RAG Server",
    lifespan=lifespan,
    redirect_slashes=False,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Router 등록
app.include_router(chat_router)
app.include_router(chatroom_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(github_auth_router)
app.include_router(github_webhook_router)
app.include_router(atlassian_auth_router)
app.include_router(jira_webhook_router)
app.include_router(slack_auth_router)
app.include_router(slack_webhook_router)
app.include_router(github_mapping_csv_router)
app.include_router(onboarding_router)
app.include_router(settings_router)
app.include_router(sync_runtime_router)


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


# 감사 로그 이벤트 리스너 등록
bus.subscribe(EventTopic.AUDIT, audit_event_handler)


# 미들웨어 등록
app.middleware("http")(request_context_middleware)


# 헬스 체크
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "message": "Catch Up backend is running."}
