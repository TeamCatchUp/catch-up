/** 소스 플랫폼 타입 */
export type SourceTypeApi = 'jira' | 'slack' | 'github' | 'unknown';

/** 소스 엔티티 타입. 'code'는 프론트 UI 전용 (github + code → 코드 출처 카드) */
export type EntityTypeApi = 'issue' | 'epic' | 'message' | 'pr' | 'comment' | 'code';

/** RAG 소스 응답 타입 */
export interface SourceResponseApi {
  // 공통 (BaseSource)
  id?: string;
  source: SourceTypeApi;
  entity_type: EntityTypeApi;
  title?: string;
  url?: string | null;
  text?: string;
  created_at?: string | null;
  updated_at?: string | null;
  author?: string | null;
  index?: number | null;
  relevance_score?: number;
  is_cited?: boolean;
  citation_rationale?: string | null;

  // github (GithubSource)
  owner?: string;
  repo?: string;
  number?: number;
  state?: string;
  labels?: string[];
  merged?: boolean;
  base_ref?: string;
  head_ref?: string;

  // jira (JiraSource)
  project_key?: string;
  issue_key?: string;
  status?: string;
  priority?: string;
  assignee?: string;

  // slack (SlackSource)
  channel_name?: string;
  team_id?: string;
  ts?: string;
  thread_ts?: string;
}
