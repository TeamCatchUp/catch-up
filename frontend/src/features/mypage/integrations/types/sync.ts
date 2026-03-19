// ─── Sync Enums (백엔드 StrEnum 매핑) ───

export type SyncConnector = 'github' | 'slack' | 'jira' | 'confluence';
export type SyncDispatchStatus = 'accepted' | 'no_events' | 'conflict' | 'failed';
export type SyncType = 'full' | 'incremental';
export type SyncTargetType = 'resource' | 'channel' | 'repository' | 'project' | 'space';
export type SyncJobStatus = 'pending' | 'in_progress' | 'success' | 'failed';

/** target(리소스) 단위 상태 — SyncJobStatus + 'retrying' */
export type SyncTargetStatus = SyncJobStatus | 'retrying';

/** GET /sync/jobs/{jobId} 및 SSE snapshot의 per-target 상태 */
export interface SyncJobTargetSnapshotItem {
  target_id: string;
  target_name: string;
  status: SyncTargetStatus;
}

// ─── API Request/Response (추후 API 연결 시 사용) ───

export interface FullSyncRequest {
  connector: SyncConnector;
  scope_id: string;
  target_ids: string[];
  sync_days?: number | null;
}

export interface SyncAcceptedResponse {
  status: SyncDispatchStatus;
  connector: SyncConnector;
  scope_id: string;
  job_id: string | null;
  event_ids: string[];
  total_targets: number;
  queued_targets: number;
  message: string | null;
  snapshot_url: string | null;
  stream_url: string | null;
}

export interface SyncJobSnapshotResponse {
  job_id: string;
  connector: SyncConnector;
  sync_type: SyncType;
  scope_id: string;
  status: SyncJobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_targets: number;
  queued_targets: number;
  processing_targets: number;
  completed_targets: number;
  failed_targets: number;
  requeued_targets: number;
  targets: SyncJobTargetSnapshotItem[];
  last_error: string | null;
  metrics: Record<string, number>;
}

/** GET /sync/status — 재진입 시 최근 상태 복원용 */
export interface SyncStatusResponse {
  connector: SyncConnector;
  scope_id: string;
  sync_type: SyncType;
  job_id: string;
  status: SyncJobStatus;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_targets: number;
  queued_targets: number;
  processing_targets: number;
  completed_targets: number;
  failed_targets: number;
  requeued_targets: number;
  last_error: string | null;
  metrics: Record<string, number>;
}

// - SyncJobSnapshotResponse: job_id 기준 조회, created_at 사용
// - SyncStatusResponse: connector+scope_id 기준 조회, requested_at 사용, job_id non-nullable

export interface SyncTargetItem {
  target_id: string;
  display_name: string;
  target_type: SyncTargetType;
  is_accessible: boolean;
  metadata: Record<string, unknown>;
}

export interface SyncTargetsResponse {
  connector: SyncConnector;
  scope_id: string;
  total_targets: number;
  targets: SyncTargetItem[];
}

// ─── Scope 선택용 타입 ───

/** GitHub scope — GET /github/installations */
export interface GithubInstallation {
  installation_id: number;
  account_login: string;
  account_type: string;
}

/** Slack scope — GET /auth/slack/status */
export interface SlackWorkspace {
  team_id: string;
  team_name: string;
}
export interface SlackInstallationStatus {
  installed: boolean;
  workspaces: SlackWorkspace[];
}

/** Atlassian scope (Jira + Confluence 공용) — GET /auth/atlassian/status */
export interface AtlassianResource {
  id: string;
  name: string;
  url: string;
  scopes: string[];
}
export interface AtlassianInstallationStatus {
  installed: boolean;
  resources: AtlassianResource[];
}

// ─── SSE Stream 타입 (GET /sync/jobs/{job_id}/stream) ───

export type SyncStreamEventType =
  | 'snapshot'
  | 'target_started'
  | 'target_completed'
  | 'target_failed'
  | 'target_requeued'
  | 'job_completed'
  | 'job_failed'
  | 'heartbeat';

/** target_* 이벤트의 payload */
export interface SyncStreamTargetPayload {
  event_id: string;
  target_id: string;
  target_name: string;
  target_type: string;
  status: string;
  sync_type: string;
  attempt: number;
}

/** snapshot 이벤트의 payload (SyncJobSnapshotResponse와 동일 구조) */
export interface SyncStreamSnapshotPayload {
  job_id: string;
  connector: SyncConnector;
  sync_type: SyncType;
  scope_id: string;
  status: SyncJobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_targets: number;
  queued_targets: number;
  processing_targets: number;
  completed_targets: number;
  failed_targets: number;
  requeued_targets: number;
  targets: SyncJobTargetSnapshotItem[];
  last_error: string | null;
  metrics: Record<string, number>;
}

/** job 종료 이벤트의 payload */
export interface SyncStreamJobEndPayload {
  status: SyncJobStatus;
  completed_at: string;
  total_targets: number;
  completed_targets: number;
  failed_targets: number;
  metrics: Record<string, number>;
}

/** SSE 이벤트 공통 필드 */
interface SyncStreamEventBase {
  connector: SyncConnector;
  job_id: string;
  scope_id: string;
  timestamp: string;
}

/** SSE 이벤트 — event_type으로 payload 타입이 결정되는 discriminated union */
export type SyncStreamEvent =
  | (SyncStreamEventBase & { event_type: 'snapshot'; payload: SyncStreamSnapshotPayload })
  | (SyncStreamEventBase & {
      event_type: 'target_started' | 'target_completed' | 'target_failed' | 'target_requeued';
      payload: SyncStreamTargetPayload;
    })
  | (SyncStreamEventBase & { event_type: 'job_completed' | 'job_failed'; payload: SyncStreamJobEndPayload })
  | (SyncStreamEventBase & { event_type: 'heartbeat'; payload: Record<string, unknown> });

// ─── UI 상태 타입 ───

/** 커넥터 카드 버튼 상태 */
export type EmbeddingButtonState = 'idle' | 'in_progress' | 'completed';

/** 임베딩 진행 현황 패널의 각 항목 */
export interface EmbeddingProgressItem {
  targetId: string;
  displayName: string;
  status: SyncTargetStatus;
}

/** 커넥터별 진행 현황 */
export interface ConnectorProgress {
  connector: SyncConnector;
  jobId: string;
  status: SyncJobStatus;
  completedTargets: number;
  totalTargets: number;
  items: EmbeddingProgressItem[];
}

// ─── 임베딩 히스토리 타입 (GET /admin/connector/status) ───

export type ConnectorStatusSource = 'github' | 'jira' | 'slack' | 'confluence';
export type ConnectorResourceType = 'repositories' | 'projects' | 'channels' | 'spaces';

/** target별 임베딩 데이터 범위 */
export interface AdminConnectorTargetRangeResponse {
  scope_id: string;
  target_id: string;
  target_name: string;
  event_id: string;
  sync_status: string;
  last_succeeded_at: string | null;
  last_failed_at: string | null;
  oldest: string | null;
  latest: string | null;
}

/** GET /admin/connector/status 응답 */
export interface AdminConnectorStatusResponse {
  source: ConnectorStatusSource;
  resource_type: ConnectorResourceType;
  total_targets: number;
  targets: AdminConnectorTargetRangeResponse[];
}

// ─── Gap & Retry API 타입 (GET /sync/records/gaps, POST /sync/records/retry) ───

export interface SyncRecordGapItem {
  record_type: string;
  expected_count: number;
  stored_count: number;
  missing_count: number;
  missing_ids: string[];
}

export interface SyncRecordGapResponse {
  connector: SyncConnector;
  scope_id: string;
  target_id: string;
  target_name: string;
  event_id: string | null;
  event_status: SyncTargetStatus | null;
  records: SyncRecordGapItem[];
}

export interface SyncRecordRetryRequestItem {
  record_type: string;
  record_ids: string[];
}

export interface SyncRecordRetryRequest {
  event_id: string;
  records: SyncRecordRetryRequestItem[];
}

export interface SyncRecordRetryResultItem {
  record_type: string;
  requested_ids: string[];
  retried_count: number;
  succeeded_count: number;
  failed_ids: string[];
  remaining_missing_ids: string[];
}

export interface SyncRecordRetryResponse {
  connector: SyncConnector;
  scope_id: string;
  target_id: string;
  target_name: string;
  event_id: string | null;
  event_status: SyncTargetStatus | null;
  records: SyncRecordRetryResultItem[];
}

export interface SyncErrorResponse {
  code: string;
  message: string;
  connector: SyncConnector | null;
  scope_id: string | null;
  metadata: Record<string, unknown>;
}
