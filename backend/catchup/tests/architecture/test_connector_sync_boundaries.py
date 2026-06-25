from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS: set[tuple[str, str]] = set()


KNOWN_CONNECTORS_CONNECTOR_CORE_IMPORTS: set[tuple[str, str]] = set()


KNOWN_CONNECTORS_SYNC_STACK_IMPORTS: set[tuple[str, str]] = set()


KNOWN_CONNECTORS_DOCUMENT_IMPORTS: set[tuple[str, str]] = set()

CONNECTOR_CORE_IMPORT = "catchup." + "connector_core"


def test_sync_and_worker_do_not_gain_connector_core_imports() -> None:
    violations = _find_imports(("catchup/sync", "catchup/worker"), (CONNECTOR_CORE_IMPORT,))

    assert violations <= KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS, _format_unexpected(
        violations,
        KNOWN_SYNC_WORKER_CONNECTOR_CORE_IMPORTS,
    )


def test_connectors_do_not_gain_connector_core_imports() -> None:
    violations = _find_imports(("catchup/connectors",), (CONNECTOR_CORE_IMPORT,))

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
        "catchup/connector_core/application/metadata_sync.py",
        "catchup/connector_core/domain/webhooks.py",
        "catchup/connector_core/ports/sync_ingestion.py",
        "catchup/connector_core/ports/metadata_sync.py",
        "catchup/sync/full_retry.py",
        "catchup/connector_core/adapters/channel_talk/metadata_sync_adapter.py",
        "catchup/connector_core/adapters/channel_talk/documents_metadata_sync_adapter.py",
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


def test_phase_11_connector_core_owner_modules_are_removed() -> None:
    for relative_path in (
        "catchup/connector_core/adapters/channel_talk",
        "catchup/connector_core/adapters/connection_status",
        "catchup/connector_core/application",
        "catchup/connector_core/descriptors",
        "catchup/connector_core/ports/connection_status.py",
        "catchup/connector_core/ports/install_auth.py",
        "catchup/connector_core/runtime",
    ):
        assert not (BACKEND_ROOT / relative_path).exists(), relative_path


def test_connector_core_directory_is_removed() -> None:
    assert not (BACKEND_ROOT / "catchup/connector_core").exists()


def test_connector_core_tests_are_moved_to_owner_packages() -> None:
    assert not (BACKEND_ROOT / "catchup/tests/connector_core").exists()


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
        "catchup/sync/metadata/channel_talk.py",
        "catchup/sync/metadata/channel_talk_documents.py",
        "catchup/sync/metadata/confluence_service.py",
        "catchup/sync/metadata/github.py",
        "catchup/sync/metadata/github_service.py",
        "catchup/sync/metadata/jira.py",
        "catchup/sync/metadata/jira_service.py",
        "catchup/sync/metadata/registry.py",
        "catchup/sync/metadata/result_store.py",
        "catchup/sync/metadata/schemas.py",
        "catchup/sync/metadata/service.py",
        "catchup/sync/metadata/slack.py",
        "catchup/sync/metadata/slack_service.py",
        "catchup/sync/metadata/slack_store.py",
    }


def test_sync_metadata_does_not_depend_on_ingestion() -> None:
    violations = _find_imports(
        ("catchup/sync/metadata",),
        ("catchup.sync.ingestion",),
    )

    assert not violations, _format_unexpected(violations, set())


def test_sync_ingestion_does_not_orchestrate_metadata() -> None:
    violations = _find_imports(
        ("catchup/sync/ingestion",),
        ("catchup.sync.metadata",),
    )

    assert not violations, _format_unexpected(violations, set())


def test_connector_services_do_not_own_metadata_sync_facades() -> None:
    for relative_path in (
        "catchup/connectors/channel_talk/service.py",
        "catchup/connectors/channel_talk/factory.py",
    ):
        imports = _imported_modules(BACKEND_ROOT / relative_path)

        assert not any(module.startswith("catchup.sync.metadata") for module in imports)
        assert not any("metadata_sync" in module for module in imports)


def test_installation_background_metadata_sync_uses_sync_registry() -> None:
    expected_imports = {
        "catchup/server/connector/slack/auth_api.py": "catchup.sync.metadata.registry",
        "catchup/server/connector/atlassian/auth_api.py": "catchup.sync.metadata.registry",
        "catchup/server/connector/channel_talk/dependencies.py": "catchup.sync.metadata.registry",
    }

    for relative_path, expected_module in expected_imports.items():
        imports = _imported_modules(BACKEND_ROOT / relative_path)

        assert expected_module in imports, relative_path


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


def test_worker_event_processor_uses_repair_full_retry_boundary() -> None:
    imports = _imported_modules(BACKEND_ROOT / "catchup/worker/worker_event_processor.py")

    assert "catchup.sync.repair.full_retry" in imports
    assert "catchup.sync.full_retry" not in imports


def test_record_repair_service_routes_through_repair_registry() -> None:
    imports = _imported_modules(BACKEND_ROOT / "catchup/sync/repair/record_repair_service.py")

    assert "catchup.sync.repair.registry" in imports
    assert not any(
        module.endswith("_record_repair_service")
        and module != "catchup.sync.repair.record_repair_service"
        for module in imports
    )


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
