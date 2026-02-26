/** mock 표시 시 반드시 포함할 상태 집합 */
export const REQUIRED_MOCK_MEMBER_STATUSES = ['완료', '미등록', '미사용'] as const;

/** 이용자 연동 목록 mock 상태 패턴 */
export const MOCK_MEMBER_STATUS_PATTERNS = [
  { github: '미사용', jira: '완료', slack: '미등록', confluence: '미사용' },
  { github: '완료', jira: '완료', slack: '완료', confluence: '미사용' },
  { github: '미등록', jira: '완료', slack: '미등록', confluence: '미사용' },
] as const;
