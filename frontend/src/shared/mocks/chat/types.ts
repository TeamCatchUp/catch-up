/**
 * Mock 데이터용 백엔드 응답 타입 (SourceResponseApi 호환)
 * features/chat/types/api/sourceApi.ts의 SourceResponseApi와 동일한 구조
 *
 * 사용처:
 * - MOCK_SOURCES (SSE 응답 시뮬레이션)
 * - MOCK_RELATED_JIRA_ISSUES (관련 Jira 이슈)
 *
 * 백엔드 RAG 타입 체계:
 * - source: "jira" | "slack" | "github" | "unknown"
 * - entity_type: "issue" | "epic" | "message" | "pr" | "comment" | "code"
 */

/** 소스 플랫폼 */
export type MockSource_Source = 'jira' | 'slack' | 'github' | 'unknown';

/** 엔티티 타입 */
export type MockSource_EntityType = 'issue' | 'epic' | 'message' | 'pr' | 'comment' | 'code';

export interface MockSource {
  // 공통 (BaseSource)
  id?: string;
  source: MockSource_Source;
  entity_type: MockSource_EntityType;
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

  // GitHub (GithubSource)
  owner?: string;
  repo?: string;
  number?: number;
  state?: string;
  labels?: string[];
  merged?: boolean;
  base_ref?: string;
  head_ref?: string;

  // Jira (JiraSource)
  project_key?: string;
  issue_key?: string;
  status?: string;
  priority?: string;
  assignee?: string;

  // Slack (SlackSource)
  channel_name?: string;
  team_id?: string;
  ts?: string;
  thread_ts?: string;
}

/**
 * Mock UI 출처 타입.
 * ChatSource 구조와 호환되도록 정의.
 */
export type MockChatSourceType = 'code' | 'pr' | 'github_issue' | 'jira' | 'slack';

/**
 * Mock UI 출처 모델.
 * @interface MockChatSource
 */
export interface MockChatSource {
  id: string;
  source_type: MockChatSourceType;
  is_cited: boolean;
  repo: string;
  title: string;
  content: string;
  date: string;
  author: string;
  html_url: string;
  source_index: number;
}

/**
 * Mock Jira 서브태스크 모델.
 * @interface MockJiraSubTask
 */
export interface MockJiraSubTask {
  id: string;
  title: string;
  issue_key?: string;
  html_url?: string;
}

/**
 * Mock Jira 태스크 모델.
 * @interface MockJiraTask
 */
export interface MockJiraTask {
  id: string;
  title: string;
  parent_key?: string;
  parent_summary?: string;
  subtasks: MockJiraSubTask[];
}

/**
 * Mock 메시지 모델.
 * @interface MockMessage
 */
export interface MockMessage {
  id: string;
  chat_history_id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: MockChatSource[];
  detailed_tasks?: MockJiraTask[];
  timestamp: string;
  has_feedback?: boolean;
}

/**
 * Mock PR payload 모델.
 * @interface MockPRPayload
 */
export interface MockPRPayload {
  pr_number: number;
  title: string;
  repo_name: string;
  summary: string;
  owner: string;
  created_at: string;
}

/**
 * Mock 스트림 이벤트 타입.
 */
export type MockStreamEvent =
  | { type: 'status'; session_id?: string; node: string; message: string }
  | { type: 'sources'; session_id?: string; sources?: MockSource[] }
  | { type: 'source_candidates'; session_id?: string; message_id?: string; sources?: MockSource[] }
  | { type: 'token'; session_id?: string; token: string }
  | { type: 'delta'; session_id?: string; message_id?: string; delta: string; sequence?: number }
  | { type: 'interrupt'; payload: MockPRPayload[] }
  | {
      type: 'result';
      session_id?: string;
      message_id?: string;
      answer?: string;
      sources?: MockSource[];
      chat_history_id?: string;
      has_feedback?: boolean;
      related_jira_issues?: MockSource[];
    }
  | { type: 'error'; session_id?: string; message: string; retryable?: boolean }
  | { type: 'ping' };

/**
 * Mock notification 데이터 타입.
 * @interface MockRagNotificationData
 */
export interface MockRagNotificationData {
  session_id: string;
  type: 'status' | 'interrupt' | 'result';
  node: string;
  message?: string;
  payload?: MockPRPayload[];
  response?: {
    session_id: string;
    answer: string;
    sources: MockSource[];
    chat_history_id: string;
    has_feedback?: boolean;
  };
  related_jira_issues?: MockSource[];
}

/**
 * Mock notification 타입.
 * @interface MockRagNotification
 */
export interface MockRagNotification {
  target: 'CHAT' | 'MESSAGE';
  type: 'CONNECT' | 'RAG_IN_PROGRESS' | 'RAG_INTERRUPT' | 'RAG_DONE';
  message: string | null;
  data: MockRagNotificationData | null;
}
