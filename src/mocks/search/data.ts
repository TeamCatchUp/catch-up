export interface ChatRoomResponse {
  sessionId: string;
  title: string;
  lastActiveTime: string;
}

export const MOCK_CHATROOMS: { content: ChatRoomResponse[] } = {
  content: [
    {
      sessionId: 'uuid-001',
      title: '로그인 관련 질문',
      lastActiveTime: '2024-01-15T10:30:00Z',
    },
    {
      sessionId: 'uuid-002',
      title: '결제 모듈 질문',
      lastActiveTime: '2024-01-14T15:20:00Z',
    },
    {
      sessionId: 'uuid-003',
      title: 'API 인증 구현 방법',
      lastActiveTime: '2024-01-13T09:15:00Z',
    },
    {
      sessionId: 'uuid-004',
      title: 'React Query 캐싱 전략',
      lastActiveTime: '2024-01-12T14:00:00Z',
    },
  ],
};

export interface RecentQueryResponse {
  query: string;
  sessionId: string;
  createdAt: string;
}

export const MOCK_RECENT_QUERIES: { content: RecentQueryResponse[] } = {
  content: [
    {
      query: '로그인 API 에러 처리 방법',
      sessionId: 'session-001',
      createdAt: '2024-01-15T10:00:00Z',
    },
    {
      query: '결제 모듈 연동 가이드',
      sessionId: 'session-002',
      createdAt: '2024-01-14T15:30:00Z',
    },
    {
      query: 'JWT 토큰 갱신 로직',
      sessionId: 'session-003',
      createdAt: '2024-01-13T09:00:00Z',
    },
    {
      query: 'React 컴포넌트 최적화 방법',
      sessionId: 'session-004',
      createdAt: '2024-01-12T11:20:00Z',
    },
    {
      query: 'TypeScript 제네릭 사용법',
      sessionId: 'session-005',
      createdAt: '2024-01-11T16:45:00Z',
    },
  ],
};

export interface JiraIssueResponse {
  issueKey: string;
  summary: string;
}

export const MOCK_JIRA_TICKETS: JiraIssueResponse[] = [
  { issueKey: 'CATCH-101', summary: '로그인 페이지 UI 개선' },
  { issueKey: 'CATCH-102', summary: '다크모드 버그 수정' },
  { issueKey: 'CATCH-103', summary: 'API 응답 속도 최적화' },
  { issueKey: 'CATCH-104', summary: '사용자 프로필 페이지 추가' },
  { issueKey: 'CATCH-105', summary: '알림 기능 구현' },
];
