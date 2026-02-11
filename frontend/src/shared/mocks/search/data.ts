export interface ChatRoomResponse {
  session_id: string;
  title: string;
  last_active_time: string;
}

export const MOCK_CHATROOMS: { content: ChatRoomResponse[] } = {
  content: [
    {
      session_id: 'uuid-001',
      title: '로그인 관련 질문',
      last_active_time: '2024-01-15T10:30:00Z',
    },
    {
      session_id: 'uuid-002',
      title: '결제 모듈 질문',
      last_active_time: '2024-01-14T15:20:00Z',
    },
    {
      session_id: 'uuid-003',
      title: 'API 인증 구현 방법',
      last_active_time: '2024-01-13T09:15:00Z',
    },
    {
      session_id: 'uuid-004',
      title: 'React Query 캐싱 전략',
      last_active_time: '2024-01-12T14:00:00Z',
    },
  ],
};

export interface RecentQueryResponse {
  query: string;
  session_id: string;
  created_at: string;
}

export const MOCK_RECENT_QUERIES: { content: RecentQueryResponse[] } = {
  content: [
    {
      query: '로그인 API 에러 처리 방법',
      session_id: 'session-001',
      created_at: '2026-01-15T10:00:00Z',
    },
    {
      query: '결제 모듈 연동 가이드',
      session_id: 'session-002',
      created_at: '2026-01-14T15:30:00Z',
    },
    {
      query: 'JWT 토큰 갱신 로직',
      session_id: 'session-003',
      created_at: '2026-01-13T09:00:00Z',
    },
    {
      query: 'React 컴포넌트 최적화 방법',
      session_id: 'session-004',
      created_at: '2026-01-12T11:20:00Z',
    },
    {
      query: 'TypeScript 제네릭 사용법',
      session_id: 'session-005',
      created_at: '2026-01-11T16:45:00Z',
    },
  ],
};
