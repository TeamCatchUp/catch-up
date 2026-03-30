from catchup.observability.langfuse.configs import init_langfuse
from catchup.observability.logging import configure_logging

# Logger 설정
configure_logging()

import asyncio
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect

from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.handlers import audit_event_handler
from catchup.audit.metadata import SystemAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.configs.config import settings
from catchup.costs.handlers import chat_token_usage_handler
from catchup.db.engine import SessionLocal
from catchup.db.engine import engine
from catchup.db.global_state import has_admin_ever_onboarded
from catchup.db.global_state import has_csv_file_ever_been_uploaded
from catchup.db.models import Base
from catchup.events.bus import bus
from catchup.events.enums import EventTopic
from catchup.events.enums import EventType
from catchup.events.enums import SystemEventAction
from catchup.observability.logging.s3_uploader import audit_log_uploader_task
from catchup.observability.logging.s3_uploader import graceful_shutdown
from catchup.rag.checkpoint import close_langgraph_checkpointer
from catchup.rag.checkpoint import init_langgraph_checkpointer
from catchup.server.admin.api import router as admin_router
from catchup.server.auth.api import router as auth_router
from catchup.server.chat.api import router as chat_router
from catchup.server.chat_room.api import router as chatroom_router
from catchup.server.costs.api import router as costs_router
from catchup.server.connector.atlassian.auth_api import router as atlassian_auth_router
from catchup.server.connector.github.auth_api import router as github_auth_router
from catchup.server.connector.github.webhook_api import router as github_webhook_router
from catchup.server.connector.jira.webhook_api import router as jira_webhook_router
from catchup.server.connector.slack.auth_api import router as slack_auth_router
from catchup.server.connector.slack.webhook_api import router as slack_webhook_router
from catchup.server.error_handlers import register_exception_handlers
from catchup.server.initialization import ensure_pg_indices
from catchup.server.mapping.api import router as github_mapping_csv_router
from catchup.server.middleware.request_context import request_context_middleware
from catchup.server.onboarding.api import router as onboarding_router
from catchup.server.settings.api import router as settings_router
from catchup.server.state import state
from catchup.server.sync.api import router as sync_runtime_router
from catchup.utils.client import _shared_client
from catchup.utils.redis import check_all_redis_health
from catchup.utils.redis import get_redis_client
from catchup.utils.redis import get_stream_redis_client
from catchup.utils.scheduler import init_scheduler
from catchup.utils.scheduler import shutdown_scheduler
from catchup.worker.worker_event_processor import run_forever as run_sync_worker

# 디버그 모드 설정
debug_mode = settings.ENV == "development" and settings.DEBUGGER_ENABLED
if debug_mode:
    import debugpy
    debugpy.listen(("0.0.0.0", settings.DEBUGGER_PORT))
    # debugpy.wait_for_client()


# Logger
logger = structlog.get_logger()


# debugpy 연결 정보 출력
if debug_mode:
    logger.info(
        "debugpy_attachment_success",
        port=settings.DEBUGGER_PORT
    )

# 버전 정보 출력
version = settings.APP_VERSION
if version:
    logger.info(
        "version_detection_success",
        app_version=version,
    )
else:
    logger.warning("version_detection_failed")


# 감사 로그 이벤트 리스너 등록
bus.subscribe(EventTopic.AUDIT, audit_event_handler)

# 토큰 사용 이벤트 리스너 등록
bus.subscribe(EventTopic.COST, chat_token_usage_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        "global_logging_config",
        context="server_startup",
        log_level=str(settings.LOG_LEVEL).upper()
    )
    
    sync_worker_stop_event: asyncio.Event | None = None
    sync_worker_task: asyncio.Task | None = None
    uploader_task: asyncio.Task | None = None  # S3 감사로그 업로드

    if settings.LOG_AUDIT_FILE_ENABLED:
        logger.info(
            "audit_file_rotation_config",
            context="server_startup",
            when=settings.LOG_AUDIT_ROTATION_WHEN,
            interval=settings.LOG_AUDIT_ROTATION_INTERVAL,
            backup_count=settings.LOG_AUDIT_BACKUP_COUNT,
        )

    if settings.AWS_S3_AUDIT_ENABLED:
        logger.info(
            "s3_audit_file_uploader_inititated",
            context="server_startup"
        )
        uploader_task = asyncio.create_task(audit_log_uploader_task())

    try:
        db_init_started_at = time.perf_counter()

        # 1) 메타데이터 기준 테이블 목록 수집
        metadata_table_names = sorted(Base.metadata.tables.keys())
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_DB_INIT,
            event_status=AuditEventStatus.ATTEMPT,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="startup_db_initialization",
                result="start",
                message="starting_db_initialization",
                metadata_table_count=len(metadata_table_names),
            ),
            immediate=True,
        )

        logger.debug(
            "metadata_tables_loaded",
            context="server_startup",
            count=len(metadata_table_names),
            tables=metadata_table_names,
        )

        # 2) create_all 이전 DB 상태 확인
        with engine.connect() as connection:
            db_inspector_before = inspect(connection)
            db_table_names_before = sorted(db_inspector_before.get_table_names())

        missing_tables_before = sorted(
            set(metadata_table_names) - set(db_table_names_before)
        )
        logger.debug(
            "db_tables_before_create_all",
            context="server_startup",
            count=len(db_table_names_before),
            tables=db_table_names_before,
        )
        logger.debug(
            "missing_tables_before_create_all",
            context="server_startup",
            count=len(missing_tables_before),
            tables=missing_tables_before,
        )

        # 3) SQLAlchemy create_all 실행
        create_all_started_at = time.perf_counter()
        Base.metadata.create_all(bind=engine)
        create_all_elapsed_ms = (time.perf_counter() - create_all_started_at) * 1000
        logger.debug(
            "create_all_completed",
            context="server_startup",
            elapsed_ms=create_all_elapsed_ms,
        )

        # 4) create_all 이후 DB 상태 확인 및 스키마 드리프트 탐지
        with engine.connect() as connection:
            db_inspector_after = inspect(connection)
            db_table_names_after = sorted(db_inspector_after.get_table_names())

            missing_columns_by_table: dict[str, list[str]] = {}
            extra_columns_by_table: dict[str, list[str]] = {}
            for table_name in metadata_table_names:
                if table_name not in db_table_names_after:
                    continue

                model_columns = sorted(Base.metadata.tables[table_name].c.keys())
                db_columns = sorted(
                    column["name"] for column in db_inspector_after.get_columns(table_name)
                )
                missing_columns = sorted(set(model_columns) - set(db_columns))
                extra_columns = sorted(set(db_columns) - set(model_columns))
                if missing_columns:
                    missing_columns_by_table[table_name] = missing_columns
                if extra_columns:
                    extra_columns_by_table[table_name] = extra_columns

        created_tables = sorted(set(db_table_names_after) - set(db_table_names_before))
        missing_tables_after = sorted(set(metadata_table_names) - set(db_table_names_after))

        logger.debug(
            "db_tables_after_create_all",
            context="server_startup",
            count=len(db_table_names_after),
            tables=db_table_names_after,
        )
        logger.debug(
            "tables_created_in_startup",
            context="server_startup",
            count=len(created_tables),
            tables=created_tables,
        )

        if missing_tables_after:
            emit_audit_event(
                event_type=EventType.SYSTEM,
                event_action=SystemEventAction.STARTUP_DB_INIT,
                event_status=AuditEventStatus.FAIL,
                level=AuditLevel.WARNING,
                metadata=SystemAuditMetadata(
                    context="startup_db_initialization",
                    result="partial_failure",
                    message="missing_tables_after_create_all",
                    missing_tables_count=len(missing_tables_after),
                    missing_tables=missing_tables_after,
                ),
                immediate=True,
            )

        if extra_columns_by_table:
            for table_name, extra_columns in extra_columns_by_table.items():
                emit_audit_event(
                    event_type=EventType.SYSTEM,
                    event_action=SystemEventAction.STARTUP_DB_SCHEMA_DRIFT,
                    event_status=AuditEventStatus.FAIL,
                    level=AuditLevel.WARNING,
                    metadata=SystemAuditMetadata(
                        context="startup_db_schema_drift",
                        result="partial_failure",
                        table_name=table_name,
                        extra_columns=extra_columns,
                    ),
                    immediate=True,
                )
        else:
            logger.debug(
                "no_extra_db_columns_detected",
                context="server_startup",
            )

        if missing_columns_by_table:
            for table_name, missing_columns in missing_columns_by_table.items():
                emit_audit_event(
                    event_type=EventType.SYSTEM,
                    event_action=SystemEventAction.STARTUP_DB_SCHEMA_DRIFT,
                    event_status=AuditEventStatus.FAIL,
                    level=AuditLevel.ERROR,
                    metadata=SystemAuditMetadata(
                        context="startup_db_schema_drift",
                        result="failure",
                        table_name=table_name,
                        missing_columns=missing_columns,
                    ),
                    immediate=True,
                )

            missing_columns_summary = ", ".join(
                f"{table_name}: {', '.join(columns)}"
                for table_name, columns in sorted(missing_columns_by_table.items())
            )
            raise RuntimeError(
                "DB schema drift detected; missing columns: "
                f"{missing_columns_summary}"
            )

        logger.debug(
            "no_missing_db_columns_detected",
            context="server_startup",
        )

        db_init_elapsed_ms = (time.perf_counter() - db_init_started_at) * 1000
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_DB_INIT,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="startup_db_initialization",
                result="success",
                elapsed_ms=round(db_init_elapsed_ms, 2),
                metadata_tables=len(metadata_table_names),
                db_tables_before=len(db_table_names_before),
                db_tables_after=len(db_table_names_after),
            ),
            immediate=True,
        )

    except Exception as e:
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_DB_INIT,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=SystemAuditMetadata(
                context="startup_db_initialization",
                result="failure",
                error=str(e),
            ),
            immediate=True,
        )
        raise

    try:
        embeddings = get_embedding_service(
            EmbeddingProvider.AWS_BEDROCK
        ).get_embedder()
        pgvector_repo = get_pgvector_repository(embeddings)  # Ingestion
        await pgvector_repo.initialize(ensure_pg_indices)
        logger.info(
            "pgvector_repository_initialized",
            result="success",
            context="server_startup",
        )
        
    except Exception as e:
        logger.error(
            "pgvector_repository_initialized",
            result="failure",
            context="server_startup",
            error=str(e),
        )
        raise


    # Langgraph Checkpoint INIT
    try:
        await init_langgraph_checkpointer()
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_CHECKPOINTER_INIT,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="startup_checkpointer_initialization",
                result="success",
            ),
            immediate=True,
        )
    except Exception as e:
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_CHECKPOINTER_INIT,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=SystemAuditMetadata(
                context="startup_checkpointer_initialization",
                result="failure",
                error=str(e),
            ),
            immediate=True,
        )
        raise

    # Scheduler 초기화
    try:
        init_scheduler()
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_SCHEDULER_INIT,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="startup_scheduler_initialization",
                result="success",
            ),
            immediate=True,
        )
    except Exception as e:
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_SCHEDULER_INIT,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=SystemAuditMetadata(
                context="startup_scheduler_initialization",
                result="failure",
                error=str(e),
            ),
            immediate=True,
        )
        raise

    try:
        await get_redis_client()
        await get_stream_redis_client()
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_REDIS_INIT,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="startup_redis_initialization",
                result="success",
            ),
            immediate=True,
        )
    except Exception as e:
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.STARTUP_REDIS_INIT,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=SystemAuditMetadata(
                context="startup_redis_initialization",
                result="failure",
                error=str(e),
            ),
            immediate=True,
        )
        raise

    if settings.SYNC_WORKER_AUTOSTART:
        sync_worker_stop_event = asyncio.Event()
        sync_worker_task = asyncio.create_task(
            run_sync_worker(sync_worker_stop_event)
        )
        logger.info(
            "in_process_worker_started",
            context="sync_worker",
        )
        
    try:
        with SessionLocal() as db:
            # 어드민 온보딩 여부 테스트
            state.is_admin_initiated = has_admin_ever_onboarded(db)
            logger.info(
                "admin_onboarding_status_checked",
                context="server_startup",
                is_admin_initiated=state.is_admin_initiated,
            )
            # 어드민 CSV 파일 최초 업로드 여부
            state.has_ever_uploaded_user_list_export = has_csv_file_ever_been_uploaded(db)
            logger.info(
                "user_list_csv_upload_status_checked",
                context="server_startup",
                has_ever_uploaded=state.has_ever_uploaded_user_list_export,
            )
            
    except Exception as e:
        logger.critical(
            "admin_initiation_check_failed",
            context="server_startup",
            error=str(e),
        )
        
    try:
        init_langfuse()
    except Exception as e:
        logger.warning(
            "langfuse_init_failed",
            context="server_startup",
            error=str(e),
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
            logger.info(
                "audit_file_flush_success",
                context="server_shutdown",
            )
        except Exception as e:
            logger.critical(
                "audit_file_flush_failed",
                context="server_shutdown",
                error=str(e),
                exc_info=True,
            )

    if sync_worker_stop_event is not None:
        sync_worker_stop_event.set()

    if sync_worker_task is not None:
        try:
            await sync_worker_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "worker_shutdown_failed",
                context="server_shutdown",
                error=str(e),
                exc_info=True,
            )

    # Scheduler Shutdown
    try:
        shutdown_scheduler()
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.SHUTDOWN_SCHEDULER,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="shutdown_scheduler",
                result="success",
            ),
            immediate=True,
        )
    except Exception as e:
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.SHUTDOWN_SCHEDULER,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=SystemAuditMetadata(
                context="shutdown_scheduler",
                result="failure",
                error=str(e),
            ),
            immediate=True,
        )

    try:
        await close_langgraph_checkpointer()
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.SHUTDOWN_CHECKPOINTER,
            event_status=AuditEventStatus.SUCCESS,
            level=AuditLevel.INFO,
            metadata=SystemAuditMetadata(
                context="shutdown_checkpointer",
                result="success",
            ),
            immediate=True,
        )
    except Exception as e:
        emit_audit_event(
            event_type=EventType.SYSTEM,
            event_action=SystemEventAction.SHUTDOWN_CHECKPOINTER,
            event_status=AuditEventStatus.FAIL,
            level=AuditLevel.ERROR,
            metadata=SystemAuditMetadata(
                context="shutdown_checkpointer",
                result="failure",
                error=str(e),
            ),
            immediate=True,
        )
        
    try:
        await _shared_client.aclose()
    except Exception as e:
        logger.error(
            "global_shared_async_client_shutdown_failed",
            context="server_shutdown",
            error=str(e),
            exc_info=True,
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

register_exception_handlers(app)

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
app.include_router(costs_router)


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

# 미들웨어 등록
if settings.PYINSTRUMENT_ENABLED:
    from catchup.server.middleware.pyinstrument import profile_middleware
    app.middleware("http")(profile_middleware)
app.middleware("http")(request_context_middleware)


# 헬스 체크
@app.get("/api/v1/health")
async def health_check():
    if not await check_all_redis_health():
        return JSONResponse(
            status_code=503,
            content={"status": "fail", "message": "Redis is unavailable."},
        )

    return {"status": "ok", "message": "Catch Up backend is running."}


# 서버 버전 체크
@app.get("/api/v1/version")
async def get_current_app_version():
    return settings.APP_VERSION
