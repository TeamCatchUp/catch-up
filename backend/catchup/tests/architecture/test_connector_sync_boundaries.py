from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS = {
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.article_full_sync"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.article_incremental"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.user_chat_full_sync"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.adapters.channel_talk.user_chat_incremental"),
    ("catchup/sync/repair/channel_talk_record_repair_service.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/channel_talk_full_sync_handler.py", "catchup.connector_core.adapters.channel_talk.article_full_sync"),
    ("catchup/worker/handlers/channel_talk_full_sync_handler.py", "catchup.connector_core.adapters.channel_talk.user_chat_full_sync"),
    ("catchup/worker/handlers/channel_talk_full_sync_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/channel_talk_full_sync_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/channel_talk_incremental_handler.py", "catchup.connector_core.adapters.channel_talk.article_incremental"),
    ("catchup/worker/handlers/channel_talk_incremental_handler.py", "catchup.connector_core.adapters.channel_talk.user_chat_incremental"),
    ("catchup/worker/handlers/channel_talk_incremental_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/channel_talk_incremental_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/confluence_full_sync_handler.py", "catchup.connector_core.adapters.confluence"),
    ("catchup/worker/handlers/confluence_full_sync_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/confluence_full_sync_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/confluence_incremental_handler.py", "catchup.connector_core.adapters.confluence"),
    ("catchup/worker/handlers/confluence_incremental_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/confluence_incremental_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/github_full_sync_handler.py", "catchup.connector_core.adapters.github"),
    ("catchup/worker/handlers/github_full_sync_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/github_full_sync_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/github_incremental_handler.py", "catchup.connector_core.adapters.github"),
    ("catchup/worker/handlers/github_incremental_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/github_incremental_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/jira_full_sync_handler.py", "catchup.connector_core.adapters.jira"),
    ("catchup/worker/handlers/jira_full_sync_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/jira_full_sync_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/jira_incremental_handler.py", "catchup.connector_core.adapters.jira"),
    ("catchup/worker/handlers/jira_incremental_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/jira_incremental_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/slack_full_sync_handler.py", "catchup.connector_core.adapters.slack"),
    ("catchup/worker/handlers/slack_full_sync_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/slack_full_sync_handler.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/worker/handlers/slack_incremental_handler.py", "catchup.connector_core.adapters.slack"),
    ("catchup/worker/handlers/slack_incremental_handler.py", "catchup.connector_core.application.sync_ingestion"),
    ("catchup/worker/handlers/slack_incremental_handler.py", "catchup.connector_core.ports.sync_ingestion"),
}


KNOWN_CONNECTORS_CONNECTOR_CORE_IMPORTS = {
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_fetcher.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.connector_core.domain.structure"),
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/connectors/channel_talk/core/user_chat_transformer.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/core/user_chat_transformer.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.connector_core.domain.structure"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.connector_core.ports.sync_ingestion"),
    ("catchup/connectors/channel_talk/document_space/article_transformer.py", "catchup.connector_core.document_format"),
    ("catchup/connectors/channel_talk/document_space/article_transformer.py", "catchup.connector_core.ports.sync_ingestion"),
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
    ("catchup/connectors/channel_talk/core/user_chat_full_sync_models.py", "catchup.sync.audit"),
    ("catchup/connectors/channel_talk/document_space/article_full_sync_models.py", "catchup.sync.audit"),
    ("catchup/connectors/confluence/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/confluence/service.py", "catchup.sync.audit"),
    ("catchup/connectors/confluence/service.py", "catchup.sync.common.schemas"),
    ("catchup/connectors/github/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/github/service.py", "catchup.sync.audit"),
    ("catchup/connectors/github/service.py", "catchup.sync.common.schemas"),
    ("catchup/connectors/github/webhook/metadata.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/github/webhook/metadata.py", "catchup.sync.ingress.types"),
    ("catchup/connectors/github/webhook/responses.py", "catchup.sync.ingress.types"),
    ("catchup/connectors/jira/factory.py", "catchup.sync.common.exceptions"),
    ("catchup/connectors/jira/service.py", "catchup.sync.audit"),
    ("catchup/connectors/jira/service.py", "catchup.sync.common.schemas"),
    ("catchup/connectors/jira/webhook/metadata.py", "catchup.sync.ingress.types"),
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
