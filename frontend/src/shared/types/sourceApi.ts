// 백엔드 `catchup/rag/schemas/sources.py` 와 1:1 동기화.
// Pydantic 상속이 JSON 직렬화 시 평면화되어 BaseSource 공통 필드와 specific 필드가 같은 레벨로 들어온다.
// `source` 가 discriminator — 값에 따라 어떤 specific 필드가 채워질지 결정.

/** 백엔드 SourceType enum과 동일 */
export type SourceTypeApi = 'jira' | 'slack' | 'github' | 'confluence' | 'channel_talk' | 'unknown';

/** 백엔드 EntityType enum과 동일 */
export type EntityTypeApi =
  | 'issue'
  | 'epic'
  | 'page'
  | 'blogpost'
  | 'message'
  | 'pr'
  | 'comment'
  | 'user_chat'
  | 'document_article';

export interface SourceResponseApi {
  // 공통 (BaseSource)
  id: string;
  source: SourceTypeApi;
  entity_type: EntityTypeApi;
  title: string;
  text: string;
  url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  author?: string | null;
  index?: number | null;
  relevance_score?: number;
  is_cited?: boolean;
  citation_rationale?: string | null;

  // jira / github / confluence 공통
  labels?: string[];

  // jira
  project_key?: string;
  issue_key?: string;
  status?: string;
  priority?: string;
  assignee?: string;

  // slack
  team_id?: string;
  ts?: string;
  thread_ts?: string;

  // github
  owner?: string;
  repo?: string;
  number?: number;
  state?: string;
  merged?: boolean;
  base_ref?: string;
  head_ref?: string;

  // confluence
  space_id?: string;
  space_key?: string;
  parent_page_id?: string;
  version?: number | string;
  chunk_index?: number;
  total_chunks?: number;
  section_hierarchy?: string[];
  has_images?: boolean;
  image_urls?: string[];

  // confluence / channel_talk 공용
  space_name?: string | null;

  // slack / channel_talk 공용
  channel_name?: string | null;

  // channel_talk
  channel_id?: string | null;
  user_chat_id?: string | null;
  article_id?: string | null;
}
