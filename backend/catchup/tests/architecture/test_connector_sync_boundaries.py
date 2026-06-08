from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS = {
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.article_full_sync"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.article_incremental"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.user_chat_full_sync"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.user_chat_incremental"),
    ("catchup/sync/handlers/channel_talk.py", "catchup.connector_core.adapters.channel_talk.article_full_sync"),
    ("catchup/sync/handlers/channel_talk.py", "catchup.connector_core.adapters.channel_talk.article_incremental"),
    ("catchup/sync/handlers/channel_talk.py", "catchup.connector_core.adapters.channel_talk.user_chat_full_sync"),
    ("catchup/sync/handlers/channel_talk.py", "catchup.connector_core.adapters.channel_talk.user_chat_incremental"),
    ("catchup/sync/handlers/confluence.py", "catchup.connector_core.adapters.confluence"),
    ("catchup/sync/handlers/github.py", "catchup.connector_core.adapters.github"),
    ("catchup/sync/handlers/jira.py", "catchup.connector_core.adapters.jira"),
    ("catchup/sync/handlers/slack.py", "catchup.connector_core.adapters.slack"),
}


KNOWN_CONNECTORS_CONNECTOR_CORE_IMPORTS = {
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.connector_core.domain.structure"),
    ("catchup/connectors/channel_talk/core/user_chat_transformer.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.connector_core.domain.structure"),
    ("catchup/connectors/channel_talk/document_space/article_transformer.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/factory.py", "catchup.connector_core.adapters.channel_talk"),
    ("catchup/connectors/channel_talk/schemas/channel_metadata.py", "catchup.connector_core.domain.structure"),
    ("catchup/connectors/channel_talk/schemas/channel_metadata.py", "catchup.connector_core.ports.metadata_sync"),
    ("catchup/connectors/channel_talk/schemas/document_metadata.py", "catchup.connector_core.domain.structure"),
    ("catchup/connectors/channel_talk/schemas/document_metadata.py", "catchup.connector_core.ports.metadata_sync"),
    ("catchup/connectors/channel_talk/service.py", "catchup.connector_core.adapters.channel_talk.documents_install_auth_adapter"),
    ("catchup/connectors/channel_talk/service.py", "catchup.connector_core.adapters.channel_talk.documents_metadata_sync_adapter"),
    ("catchup/connectors/channel_talk/service.py", "catchup.connector_core.adapters.channel_talk.install_auth_adapter"),
    ("catchup/connectors/channel_talk/service.py", "catchup.connector_core.adapters.channel_talk.metadata_sync_adapter"),
    ("catchup/connectors/channel_talk/service.py", "catchup.connector_core.application.install_auth"),
    ("catchup/connectors/channel_talk/service.py", "catchup.connector_core.application.metadata_sync"),
    ("catchup/connectors/jira/transformers.py", "catchup.connector_core.document_format"),
}


KNOWN_CONNECTORS_SYNC_STACK_IMPORTS = {
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_fetcher.py", "catchup.sync.ingestion.schemas"),
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.sync.audit"),
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.sync.ingestion.schemas"),
    ("catchup/connectors/channel_talk/core/user_chat_transformer.py", "catchup.sync.ingestion.schemas"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.sync.audit"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.sync.ingestion.schemas"),
    ("catchup/connectors/channel_talk/document_space/article_transformer.py", "catchup.sync.ingestion.schemas"),
    ("catchup/connectors/confluence/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/confluence/service.py", "catchup.sync.audit"),
    ("catchup/connectors/confluence/service.py", "catchup.sync.common.schemas"),
    ("catchup/connectors/github/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/github/service.py", "catchup.sync.audit"),
    ("catchup/connectors/github/service.py", "catchup.sync.common.schemas"),
    ("catchup/connectors/github/webhook/responses.py", "catchup.sync.ingress.types"),
    ("catchup/connectors/jira/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/jira/service.py", "catchup.sync.audit"),
    ("catchup/connectors/jira/service.py", "catchup.sync.common.schemas"),
    ("catchup/connectors/jira/webhook/responses.py", "catchup.sync.ingress.types"),
    ("catchup/connectors/slack/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/slack/ingestion_service.py", "catchup.sync.audit"),
    ("catchup/connectors/slack/ingestion_service.py", "catchup.sync.common.schemas"),
}


KNOWN_CONNECTORS_DOCUMENT_IMPORTS = {
    ("catchup/connectors/confluence/transformers.py", "langchain_core.documents"),
    ("catchup/connectors/github/service.py", "langchain_core.documents"),
    ("catchup/connectors/github/transformers.py", "langchain_core.documents"),
    ("catchup/connectors/jira/service.py", "langchain_core.documents"),
    ("catchup/connectors/jira/transformers.py", "langchain_core.documents"),
    ("catchup/connectors/slack/ingestion_service.py", "langchain_core.documents"),
    ("catchup/connectors/slack/transformers.py", "langchain_core.documents"),
}


def test_sync_and_worker_do_not_gain_connector_core_imports() -> None:
    violations = _find_imports(("catchup/sync", "catchup/worker"), ("catchup.connector_core",))

    assert violations <= KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS, _format_unexpected(
        violations,
        KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS,
    )


def test_connectors_do_not_gain_connector_core_imports() -> None:
    violations = _find_imports(("catchup/connectors",), ("catchup.connector_core",))

    assert violations <= KNOWN_CONNECTORS_CONNECTOR_CORE_IMPORTS, _format_unexpected(
        violations,
        KNOWN_CONNECTORS_CONNECTOR_CORE_IMPORTS,
    )


def test_connectors_do_not_gain_sync_stack_imports() -> None:
    violations = _find_imports(
        ("catchup/connectors",),
        (
            "catchup.sync",
            "catchup.worker",
            "catchup.server.sync",
            "catchup.db.sync",
        ),
    )

    assert violations <= KNOWN_CONNECTORS_SYNC_STACK_IMPORTS, _format_unexpected(
        violations,
        KNOWN_CONNECTORS_SYNC_STACK_IMPORTS,
    )


def test_connectors_do_not_gain_document_build_imports() -> None:
    violations = _find_imports(("catchup/connectors",), ("langchain_core.documents",))

    assert violations <= KNOWN_CONNECTORS_DOCUMENT_IMPORTS, _format_unexpected(
        violations,
        KNOWN_CONNECTORS_DOCUMENT_IMPORTS,
    )


def test_compatibility_wrapper_modules_are_removed() -> None:
    for relative_path in (
        "catchup/worker/registry.py",
        "catchup/worker/common/handlers.py",
        "catchup/connector_core/application/sync_ingestion.py",
        "catchup/connector_core/application/sync_ingestion_logging.py",
        "catchup/connector_core/domain/webhooks.py",
        "catchup/connector_core/ports/sync_ingestion.py",
        "catchup/connectors/github/webhook/metadata.py",
        "catchup/connectors/jira/webhook/metadata.py",
        "catchup/connectors/slack/webhook/metadata.py",
        "catchup/connectors/slack/webhook_service.py",
        "catchup/server/connector/slack/webhook_dispatcher.py",
        "catchup/worker/handlers/base_incremental_handler.py",
        "catchup/worker/handlers/base_full_sync_handler.py",
        "catchup/worker/handlers/channel_talk_incremental_handler.py",
        "catchup/worker/handlers/channel_talk_full_sync_handler.py",
        "catchup/worker/handlers/confluence_incremental_handler.py",
        "catchup/worker/handlers/confluence_full_sync_handler.py",
        "catchup/worker/handlers/github_incremental_handler.py",
        "catchup/worker/handlers/github_full_sync_handler.py",
        "catchup/worker/handlers/jira_incremental_handler.py",
        "catchup/worker/handlers/jira_full_sync_handler.py",
        "catchup/worker/handlers/slack_full_sync_handler.py",
        "catchup/worker/handlers/slack_incremental_handler.py",
        "catchup/worker/handlers/__init__.py",
    ):
        assert not (BACKEND_ROOT / relative_path).exists(), relative_path


def test_connector_webhook_modules_do_not_own_db_write_path() -> None:
    violations = _find_imports(
        (
            "catchup/connectors/github/webhook",
            "catchup/connectors/jira/webhook",
            "catchup/connectors/slack/webhook",
        ),
        (
            "catchup.db",
            "sqlalchemy",
            "fastapi.concurrency",
        ),
    )

    assert not violations, _format_unexpected(violations, set())


def test_sync_ingress_package_stays_as_webhook_entrypoint() -> None:
    actual_files = {
        path.relative_to(BACKEND_ROOT).as_posix()
        for path in (BACKEND_ROOT / "catchup/sync/ingress").glob("*.py")
    }

    assert actual_files == {
        "catchup/sync/ingress/__init__.py",
        "catchup/sync/ingress/github.py",
        "catchup/sync/ingress/jira.py",
        "catchup/sync/ingress/slack.py",
        "catchup/sync/ingress/types.py",
    }


def test_sync_metadata_package_owns_webhook_metadata_state_writes() -> None:
    actual_files = {
        path.relative_to(BACKEND_ROOT).as_posix()
        for path in (BACKEND_ROOT / "catchup/sync/metadata").glob("*.py")
    }

    assert actual_files == {
        "catchup/sync/metadata/__init__.py",
        "catchup/sync/metadata/github.py",
        "catchup/sync/metadata/jira.py",
        "catchup/sync/metadata/slack.py",
        "catchup/sync/metadata/slack_store.py",
    }


def test_jira_dynamic_webhook_service_is_connector_lifecycle_capability() -> None:
    assert (
        BACKEND_ROOT / "catchup/connectors/jira/dynamic_webhook_service.py"
    ).exists()
    assert not (
        BACKEND_ROOT / "catchup/sync/ingress/jira_dynamic_webhook_service.py"
    ).exists()


def test_server_webhook_api_uses_sync_ingress_for_product_dispatch() -> None:
    expected_imports = {
        "catchup/server/connector/github/webhook_api.py": "catchup.sync.ingress.github",
        "catchup/server/connector/jira/webhook_api.py": "catchup.sync.ingress.jira",
        "catchup/server/connector/slack/webhook_api.py": "catchup.sync.ingress.slack",
    }

    for relative_path, expected_module in expected_imports.items():
        imports = _imported_modules(BACKEND_ROOT / relative_path)

        assert expected_module in imports, relative_path


def test_worker_processors_use_canonical_handler_registry() -> None:
    for relative_path in (
        "catchup/worker/full_sync_processor.py",
        "catchup/worker/incremental_processor.py",
    ):
        imports = _imported_modules(BACKEND_ROOT / relative_path)

        assert "catchup.sync.handlers.registry" in imports, relative_path


def test_slack_sync_handlers_do_not_import_worker_modules() -> None:
    imports = _imported_modules(BACKEND_ROOT / "catchup/sync/handlers/slack.py")

    assert not any(module.startswith("catchup.worker") for module in imports)


def test_canonical_sync_handlers_do_not_import_worker_modules() -> None:
    for relative_path in (
        "catchup/sync/handlers/channel_talk.py",
        "catchup/sync/handlers/confluence.py",
        "catchup/sync/handlers/github.py",
        "catchup/sync/handlers/jira.py",
        "catchup/sync/handlers/slack.py",
    ):
        imports = _imported_modules(BACKEND_ROOT / relative_path)

        assert not any(module.startswith("catchup.worker") for module in imports), (
            relative_path
        )


def _find_imports(
    roots: tuple[str, ...],
    forbidden_prefixes: tuple[str, ...],
) -> set[tuple[str, str]]:
    violations: set[tuple[str, str]] = set()
    for root in roots:
        for path in sorted((BACKEND_ROOT / root).rglob("*.py")):
            relative_path = path.relative_to(BACKEND_ROOT).as_posix()
            for module in _imported_modules(path):
                if _matches_any_prefix(module, forbidden_prefixes):
                    violations.add((relative_path, module))
    return violations


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _matches_any_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _format_unexpected(
    violations: set[tuple[str, str]],
    allowlist: set[tuple[str, str]],
) -> str:
    unexpected = sorted(violations - allowlist)
    return "Unexpected boundary imports:\n" + "\n".join(
        f"- {path}: {module}" for path, module in unexpected
    )
