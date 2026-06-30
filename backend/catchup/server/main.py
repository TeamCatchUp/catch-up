from catchup.observability.langfuse.configs import init_langfuse
from catchup.observability.logging import configure_logging

# Logger 설정
configure_logging()

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from catchup.agents.tools import init_agent_tool_registry
from catchup.agents.triggers.listener import run_agent_trigger_listener_forever
from catchup.agents.triggers.recovery import run_debounce_ttl_listener_forever
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.handlers import audit_event_handler
from catchup.audit.metadata import SystemAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.configs.config import settings
from catchup.costs.handlers import chat_token_usage_handler
from catchup.db.engine import SessionLocal
from catchup.db.global_state import has_admin_ever_onboarded
from catchup.db.global_state import has_csv_file_ever_been_uploaded
from catchup.db.user_source_mapping import reconcile_missing_user_source_mappings
from catchup.events.bus import bus
from catchup.events.enums import EventTopic
from catchup.events.enums import EventType
from catchup.events.enums import SystemEventAction
from catchup.observability.logging.s3_uploader import audit_log_uploader_task
from catchup.observability.logging.s3_uploader import graceful_shutdown
from catchup.rag.checkpoint import close_langgraph_checkpointer
from catchup.rag.checkpoint import init_langgraph_checkpointer
from catchup.rag.executors import rag_executors
from catchup.rag.semaphores import rag_semaphores
from catchup.server.admin.api import router as admin_router
from catchup.server.audit.api import router as audit_router
from catchup.server.auth.api import router as auth_router
from catchup.server.automations.api import router as inquiry_automation_router
from catchup.server.chat.api import router as chat_router
from catchup.server.chat_room.api import router as chatroom_router
from catchup.server.connector.atlassian.auth_api import router as atlassian_auth_router
from catchup.server.connector.channel_talk.admin_api import (
    router as channel_talk_admin_router,
)
from catchup.server.connector.channel_talk.webhook_api import (
    router as channel_talk_webhook_router,
)
from catchup.server.connector.github.auth_api import router as github_auth_router
from catchup.server.connector.github.webhook_api import router as github_webhook_router
from catchup.server.connector.jira.webhook_api import router as jira_webhook_router
from catchup.server.connector.slack.auth_api import router as slack_auth_router
from catchup.server.connector.slack.webhook_api import router as slack_webhook_router
from catchup.server.error_handlers import register_exception_handlers
from catchup.server.initialization import ensure_ks_all_indices
from catchup.server.initialization import ensure_pg_indices
from catchup.server.initialization import ensure_vector_index
from catchup.server.integrations.api import router as integrations_router
from catchup.server.mapping.api import router as github_mapping_csv_router
from catchup.server.mcp.install_api import router as mcp_install_router
from catchup.server.mcp.oauth_api import router as mcp_oauth_router
from catchup.server.mcp.oauth_api import well_known_router as mcp_well_known_router
from catchup.server.middleware.request_context import RequestContextMiddleware
from catchup.server.onboarding.api import router as onboarding_router
from catchup.server.search.api import router as search_router
from catchup.server.settings.api import router as settings_router
from catchup.server.state import state
from catchup.server.stats.api import router as stats_router
from catchup.server.sync.api import router as sync_runtime_router
from catchup.server.workflow_credentials.api import (
    router as workflow_credentials_router,
)
from catchup.utils.client import _shared_client
from catchup.utils.redis import check_all_redis_health
from catchup.utils.redis import get_redis_client
from catchup.utils.redis import get_stream_redis_client
from catchup.utils.scheduler import init_scheduler
from catchup.utils.scheduler import shutdown_scheduler
from catchup.worker.worker_event_processor import run_forever as run_sync_worker
from catchup.workflows import init_workflow_node_registry

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
    logger.info("debugpy_attachment_success", port=settings.DEBUGGER_PORT)

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
        log_level=str(settings.LOG_LEVEL).upper(),
    )

    sync_worker_stop_event: asyncio.Event | None = None
    sync_worker_task: asyncio.Task | None = None
    agent_trigger_listener_stop_event: asyncio.Event | None = None
    agent_trigger_listener_task: asyncio.Task | None = None
    debounce_ttl_listener_stop_event: asyncio.Event | None = None
    debounce_ttl_listener_task: asyncio.Task | None = None
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
        logger.info("s3_audit_file_uploader_inititated", context="server_startup")
        uploader_task = asyncio.create_task(audit_log_uploader_task())

    # TODO: depenendcy-injector 기반으로 생명 주기 관리 검토
    # Ingestion용 pgvector_repo 생성
    try:
        embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
        pgvector_repo = get_pgvector_repository(embeddings)  # Ingestion
        await pgvector_repo.initialize(ensure_pg_indices)
        if settings.VECTOR_STORE_V2_DUAL_WRITE_ENABLED:
            v2_vector_store = get_v2_vector_store(embeddings)
            await v2_vector_store.initialize()
        if settings.PGVECTOR_HNSW_INDEX_ENABLED:
            asyncio.create_task(ensure_vector_index())
        asyncio.create_task(ensure_ks_all_indices())
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

    try:
        rag_semaphores.init(
            small_llm_value=settings.AWS_BEDROCK_SMALL_MODEL_SEMA_VALUE,
            large_llm_value=settings.AWS_BEDROCK_LARGE_MODEL_SEMA_VALUE,
            reranker_value=settings.AWS_BEDROCK_RERANK_SEMA_VALUE,
        )
        rag_executors.init(
            vector_search_size=settings.RAG_VECTOR_SEARCH_THREAD_POOL_SIZE,
            rerank_size=settings.RAG_BEDROCK_RERANK_THREAD_POOL_SIZE,
            llm_size=settings.RAG_LLM_THREAD_POOL_SIZE,
        )
    except:
        # TODO: emit_audit_event()
        logger.error("langgraph_semaphore_init_failed", exc_info=True)
        raise

    try:
        init_workflow_node_registry()
        logger.info("workflow_node_registry_initialized", context="server_startup")
    except Exception as e:
        logger.warning(
            "workflow_node_registry_init_failed",
            context="server_startup",
            error=str(e),
        )

    try:
        init_agent_tool_registry()
        logger.info("agent_tool_registry_initialized", context="server_startup")
    except Exception as e:
        logger.warning(
            "agent_tool_registry_init_failed",
            context="server_startup",
            error=str(e),
        )

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
        sync_worker_task = asyncio.create_task(run_sync_worker(sync_worker_stop_event))
        logger.info(
            "in_process_worker_started",
            context="sync_worker",
        )
    if settings.AGENT_TRIGGER_WORKER_AUTOSTART:
        agent_trigger_listener_stop_event = asyncio.Event()
        agent_trigger_listener_task = asyncio.create_task(
            run_agent_trigger_listener_forever(agent_trigger_listener_stop_event)
        )
        debounce_ttl_listener_stop_event = asyncio.Event()
        debounce_ttl_listener_task = asyncio.create_task(
            run_debounce_ttl_listener_forever(debounce_ttl_listener_stop_event)
        )
        logger.info(
            "in_process_worker_started",
            context="agent_trigger_worker",
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
            state.has_ever_uploaded_user_list_export = has_csv_file_ever_been_uploaded(
                db
            )
            logger.info(
                "user_list_csv_upload_status_checked",
                context="server_startup",
                has_ever_uploaded=state.has_ever_uploaded_user_list_export,
            )
            # is_registered=True이지만 UserSourceMapping이 없는 항목 일괄 해소 (임시 조치)
            resolved_count = reconcile_missing_user_source_mappings(db)
            db.commit()
            logger.info(
                "user_source_mapping_reconciled",
                context="server_startup",
                resolved_count=resolved_count,
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

    if settings.MCP_SERVER_ENABLED:
        from catchup.mcp.server import mcp as _mcp_server
        async with _mcp_server.session_manager.run():
            yield
    else:
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
    if agent_trigger_listener_stop_event is not None:
        agent_trigger_listener_stop_event.set()
    if debounce_ttl_listener_stop_event is not None:
        debounce_ttl_listener_stop_event.set()

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
    if agent_trigger_listener_task is not None:
        try:
            await agent_trigger_listener_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "agent_trigger_listener_shutdown_failed",
                context="server_shutdown",
                error=str(e),
                exc_info=True,
            )
    if debounce_ttl_listener_task is not None:
        try:
            await debounce_ttl_listener_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "agent_trigger_debounce_ttl_listener_shutdown_failed",
                context="server_shutdown",
                error=str(e),
                exc_info=True,
            )

    try:
        rag_executors.shutdown(cancel_futures=True)
        logger.info("rag_executors_shutdown", context="server_shutdown")
    except Exception as e:
        logger.error(
            "rag_executors_shutdown_failed",
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
    docs_url="/api/docs" if settings.API_DOCS_ENABLED else None,
    redoc_url="/api/redoc" if settings.API_DOCS_ENABLED else None,
    openapi_url="/api/openapi.json" if settings.API_DOCS_ENABLED else None,
)

register_exception_handlers(app)

# Router 등록
app.include_router(chat_router)
app.include_router(chatroom_router)
app.include_router(auth_router)
app.include_router(integrations_router)
app.include_router(admin_router)
app.include_router(inquiry_automation_router)
app.include_router(channel_talk_admin_router)
app.include_router(channel_talk_webhook_router)
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
app.include_router(stats_router)
app.include_router(search_router)
app.include_router(audit_router)
app.include_router(workflow_credentials_router)

if settings.DEBUG_API_ENABLED:
    from catchup.server.debug.agent_simulate import router as agent_simulate_router
    from catchup.server.debug.retrieval_v2_probe import (
        router as retrieval_v2_probe_router,
    )
    from catchup.server.debug.search_probe import router as search_probe_router
    app.include_router(search_probe_router)
    app.include_router(agent_simulate_router)
    app.include_router(retrieval_v2_probe_router)
    logger.warning("debug_api_enabled", note="disable DEBUG_API_ENABLED in production")

app.include_router(mcp_well_known_router)
app.include_router(mcp_oauth_router)
# mcp_install_router는 반드시 app.mount("/api/v1/mcp", ...) 보다 먼저 등록해야 한다.
# Starlette는 삽입 순서로 라우트를 평가하므로 순서가 바뀌면 install 엔드포인트가
# MCPAuthMiddleware mount에 흡수되어 403을 반환한다.
app.include_router(mcp_install_router)

if settings.MCP_SERVER_ENABLED:
    from fastapi.responses import RedirectResponse

    from catchup.mcp.server import mcp as mcp_server
    from catchup.server.middleware.mcp_auth import MCPAuthMiddleware

    @app.api_route("/api/v1/mcp", methods=["GET", "POST", "DELETE"])
    async def _mcp_slash_redirect():
        return RedirectResponse(url="/api/v1/mcp/", status_code=307)

    app.mount("/api/v1/mcp", MCPAuthMiddleware(mcp_server.streamable_http_app()))


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",  # Go Live 포트 허용
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
app.add_middleware(RequestContextMiddleware)


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
