/**
 * Backend source types
 * Used for SSE response parsing and API communication
 * Feature-specific types for chat domain
 *
 * 백엔드 RAG 타입 체계 (catchup/rag/schemas/sources.py)
 * - source: "jira" | "slack" | "github" | "unknown"
 * - entity_type: "issue" | "epic" | "message" | "pr" | "comment" | "code"
 */

/** 소스 플랫폼 (backend SourceType StrEnum) */
export type BackendSource_Source = 'jira' | 'slack' | 'github' | 'unknown';

/** 엔티티 타입 (backend EntityType StrEnum + code) */
export type BackendSource_EntityType = 'issue' | 'epic' | 'message' | 'pr' | 'comment' | 'code';

export interface BackendSource {
  index: number;
  is_cited: boolean;
  source: BackendSource_Source;
  entity_type: BackendSource_EntityType;
  relevance_score: number;
  html_url?: string;
  content: string;
  owner: string;

  // github
  repo?: string;
  file_path?: string;
  days_ago?: number;
  title?: string;
  pr_number?: number;
  created_at?: number;
  author?: string;

  // jira
  issue_key?: string;
  summary?: string;
  project_name?: string;
  parent_key?: string;
  parent_summary?: string;
  assignee_name?: string;
  status_id?: number;

  // slack
  channel_name?: string;
  team_id?: string;
  ts?: string;
  thread_ts?: string;
}
