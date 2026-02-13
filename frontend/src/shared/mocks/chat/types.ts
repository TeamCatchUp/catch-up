/**
 * Mock 데이터용 백엔드 응답 타입 (BackendSource 호환)
 * features/chat/types/source.d.ts의 BackendSource와 동일한 구조
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
  /** 소스 인덱스 */
  index: number;
  /** 답변에서 인용 여부 */
  is_cited: boolean;
  /** 소스 플랫폼 */
  source: MockSource_Source;
  /** 엔티티 타입 */
  entity_type: MockSource_EntityType;
  /** 관련도 점수 */
  relevance_score: number;
  /** 소스 URL */
  html_url?: string;
  /** 소스 내용 */
  content: string;
  /** 저장소/프로젝트 소유자 */
  owner: string;

  // GitHub 관련 필드
  /** 저장소명 */
  repo?: string;
  /** 파일 경로 */
  file_path?: string;
  /** 파일 카테고리 (예: controller, service) */
  category?: string;
  /** 프로그래밍 언어 */
  language?: string;
  /** 며칠 전 */
  days_ago?: number;
  /** PR/이슈 제목 */
  title?: string;
  /** PR 번호 */
  pr_number?: number;
  /** PR 상태 (open, merged, closed) */
  state?: string;
  /** 생성 시각 (Unix timestamp) */
  created_at?: number;
  /** 작성자 */
  author?: string;

  // Jira 관련 필드
  /** 이슈 키 (예: CATCH-101) */
  issue_key?: string;
  /** 이슈 타입 (Bug, Task, Story 등) */
  issueTypeName?: string;
  /** 이슈 요약 */
  summary?: string;
  /** 프로젝트명 */
  project_name?: string;
  /** 상위 이슈 키 */
  parent_key?: string;
  /** 상위 이슈 요약 */
  parent_summary?: string;
  /** 담당자명 */
  assignee_name?: string;
  /** 상태 ID */
  status_id?: number;

  // Slack 관련 필드
  /** 채널명 */
  channel_name?: string;
  /** 워크스페이스 ID */
  team_id?: string;
  /** 타임스탬프 */
  ts?: string;
  /** 스레드 부모 TS */
  thread_ts?: string;
}
