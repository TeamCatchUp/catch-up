# Channel Talk Phase 3 Task 5 Boundary Memo

Date: 2026-04-22
Worker: worker-1
Purpose: lock the implementation boundary before the real full-sync integration lands.

## Verified baseline

- Shared runtime admission is already wired for `channel_talk`:
  - `backend/catchup/db/models.py`
  - `backend/catchup/server/sync/schemas.py`
  - `backend/catchup/sync/full/registry.py`
  - `backend/catchup/sync/query_service.py`
  - `backend/catchup/worker/registry.py`
  - `backend/catchup/worker/handlers/channel_talk_full_sync_handler.py`
- `connector_core` already owns the typed full-sync contract and logical metadata contract:
  - `backend/catchup/connector_core/ports/full_sync.py`
  - `backend/catchup/connector_core/application/full_sync.py`
  - `backend/catchup/connector_core/adapters/channel_talk/full_sync_adapter.py`
  - `backend/catchup/connector_core/document_format/channel_talk.py`
- Raw Channel Talk full-sync fetch surfaces already exist in the vendor layer:
  - `backend/catchup/connectors/channel_talk/client.py`
  - `backend/catchup/connectors/channel_talk/schemas.py`
- `db/channel_talk` is currently row-CRUD oriented and should stay that way:
  - `backend/catchup/db/channel_talk/repository.py`

## Exact boundary: shared runtime (`server/sync`, `sync`, `worker`)

Owns only:
- `POST /api/v1/sync/full`, `/targets`, `/status` request/response envelopes.
- `SyncConnector.CHANNEL_TALK` admission and handler registration.
- Singleton runtime bootstrap target exposure for `target_id=user_chat`.
- Job/event dispatch lifecycle, queue publication, and generic success/failure accounting.
- Conversion from shared `FullSyncContext` into a Channel Talk execution request containing only tenant identity and time window.

Must not own:
- Channel Talk raw endpoint order (`list -> detail -> messages`).
- `next` / cursor pagination semantics, quota-header interpretation, or retry timing semantics.
- Which messages are included/excluded in a logical document.
- `page_content`, `contextual_content`, or `cmetadata` projection rules.
- Channel Talk detail/message payload field interpretation beyond validating `scope_id` and `target_id`.

Current code that should stay thin:
- `backend/catchup/sync/query_service.py` may validate that a Channel Talk connection exists and may expose the singleton target, but it must not grow fetch/pagination/document logic.
- `backend/catchup/worker/handlers/channel_talk_full_sync_handler.py` may validate `scope_id`, validate `target_id=user_chat`, build `FullSyncWindow`, and invoke `ConnectorFullSyncApplication`; it must not start reading raw API payload shapes.

## Exact boundary: `connector_core`

Owns:
- The typed full-sync pipeline contract (`fetch -> transform -> summarize -> persist -> build_result`).
- Channel Talk full-sync execution request/checkpoint/result models.
- The policy that one `UserChat` plus included `Messages` becomes one logical document.
- Logical document construction, including:
  - `page_content`
  - `contextual_content`
  - flat-compatible `cmetadata` projection via `to_storage_metadata()`
- Normalizing vendor payloads into connector-owned canonical structures before persistence.
- The orchestration that decides when vendor fetch results become persisted documents.

Must not own:
- Raw `httpx` request execution or raw header parsing.
- SQLAlchemy row CRUD for Channel Talk tables.
- Shared job/event state transitions or FastAPI route handling.

Task 5 implementation rule:
- The currently stubbed methods in `backend/catchup/connector_core/adapters/channel_talk/full_sync_adapter.py` (`transform`, `summarize`, `persist`) should be completed here or in Channel Talk adapter-owned helpers under `connector_core`, not by pushing document rules upward into shared runtime.

## Exact boundary: `connectors/channel_talk`

Owns:
- Channel Talk Open API endpoints, request headers, and parameter formation.
- Parsing list/detail/message payloads into typed vendor-facing models.
- Pagination cursors and quota/retry header snapshots.
- Recovering author, form, log, button, file, and web-page payload details from raw API responses.

Must not own:
- Shared sync dispatch/job/event lifecycle.
- PGVector/document persistence orchestration.
- The shared logical document contract (`DocumentBaseMetadata`, flat `cmetadata` projection rules).
- Cross-connector runtime semantics.

Implementation rule:
- If Task 5 needs more fetch helpers, add them in `connectors/channel_talk/*` only when they are still raw-API concerns. Do not let this layer decide document inclusion policy or storage layout.

## Exact boundary: `db/channel_talk`

Owns:
- SQLAlchemy row CRUD for Channel Talk credentials/metadata tables.
- Row lookup/upsert/delete mechanics and row-to-schema mapping for DB-backed records.

Must not own:
- Full-sync orchestration.
- Channel Talk API fetching.
- Document assembly.
- PGVector upsert/delete orchestration unless a later task explicitly creates a dedicated persistence seam.

Current constraint:
- Do not add new checkpoint/run tables or broaden `db/channel_talk` into a workflow layer in Task 5.

## Architecture watchouts for worker-2 / follow-up reviewers

- Keep the shared runtime blind to Channel Talk raw semantics; the only shared-runtime facts should remain `connector=channel_talk`, `scope_id`, `target_id=user_chat`, and the generic sync window.
- The `connector_core` adapter is the right place to decide which message records become part of the single logical `UserChat` document.
- Preserve the existing nested logical metadata + flat storage projection split; do not introduce a nested physical `cmetadata` migration in this task.
- If persistence needs a new collaborator, prefer a narrow adapter-local seam rather than teaching `worker/*` or `sync/*` how Channel Talk documents are built.
