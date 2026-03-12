// ─── Sync Enums (백엔드 StrEnum 매핑) ───

export type SyncConnector = 'github' | 'slack' | 'jira' | 'confluence';
export type SyncDispatchStatus = 'accepted' | 'no_events' | 'conflict' | 'failed';
export type SyncType = 'full' | 'incremental';
export type SyncTargetType = 'resource' | 'channel' | 'repository' | 'project' | 'space';
export type SyncJobStatus = 'pending' | 'in_progress' | 'success' | 'failed';

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

// ─── UI 상태 타입 ───

/** 커넥터 카드 버튼 상태 */
export type EmbeddingButtonState = 'idle' | 'in_progress' | 'completed';

/** 임베딩 진행 현황 패널의 각 항목 */
export interface EmbeddingProgressItem {
  targetId: string;
  displayName: string;
  status: SyncJobStatus;
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
