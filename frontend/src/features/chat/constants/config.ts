/** RAG 관련 상수 정의 */

/**
 * 백엔드 노드 이름 -> UI 단계 매핑
 * null은 UI에 표시하지 않는 노드를 의미
 */
export const NODE_TO_UI_STEP: Record<string, RagUIStepKey | null> = {
  router: 'router',
  rewrite: 'router',
  plan: 'retrieve',
  retrieve: 'retrieve',
  rerank: 'rerank',
  manage_pr_context: null,
  grade: 'grade',
  generate: 'generate',
  chitchat: 'generate',
} as const;

/**
 * 팀 스페이스 옵션
 */
export const TEAM_SPACES = [
  { id: 'fe', name: 'Catch Up | FE' },
  { id: 'be', name: 'Catch Up | BE' },
  { id: 'pm', name: 'Catch Up | 기획' },
  { id: 'design', name: 'Catch Up | Design' },
] as const;

export type TeamSpace = (typeof TEAM_SPACES)[number];

/**
 * 인덱스 리스트 (하드코딩된 값 - 추후 동적으로 변경 예정)
 */
export const HARD_CODED_INDEX_LIST = [
  'CatchUp_BE_develop_code',
  'CatchUp_BE_develop_pr',
  'cu_jira_issue',
] as const;

/**
 * 휠 네비게이션 설정
 */
export const WHEEL_CONFIG = {
  /** 페이지 전환을 위한 휠 임계값 (트랙패드: 60~100, 마우스: 100~200) */
  THRESHOLD: 75,
  /** 휠 입력이 끝났다고 판단하는 시간 (ms) */
  END_MS: 100,
} as const;

/**
 * 애니메이션 설정
 */
export const ANIMATION_CONFIG = {
  /** 슬라이드 전환 시간 (ms) */
  SLIDE_DURATION_MS: 300,
} as const;

/**
 * SSE 설정
 */
export const SSE_CONFIG = {
  /** 연결 타임아웃 (ms) */
  TIMEOUT_MS: 30000,
} as const;

/**
 * localStorage 키 생성
 */
export const getStorageKeys = (sessionId: string) => ({
  chat: `chat_${sessionId}`,
  page: `chat_${sessionId}_currentPage`,
});

/**
 * 답변 아이콘 목록
 */
export { RAG_UI_STEPS } from './steps';
