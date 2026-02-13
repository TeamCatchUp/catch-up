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
    // 오늘 (5개)
    {
      query: '일본 시장 진출 전체 진행 상황 요약 및 분석',
      session_id: 'mock-today-1',
      created_at: new Date().toISOString(),
    },
    {
      query: 'Q4 매출 분석 리포트 작성 가이드',
      session_id: 'mock-today-2',
      created_at: new Date().toISOString(),
    },
    {
      query: '신규 프로젝트 예산 편성 방법',
      session_id: 'mock-today-3',
      created_at: new Date().toISOString(),
    },
    {
      query: '팀 미팅 일정 조율 및 안건 정리',
      session_id: 'mock-today-4',
      created_at: new Date().toISOString(),
    },
    {
      query: '월간 KPI 달성 현황 점검',
      session_id: 'mock-today-5',
      created_at: new Date().toISOString(),
    },

    // 최근 7일 (4개)
    {
      query: '경쟁사 분석 자료 수집 및 정리',
      session_id: 'mock-week-1',
      created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      query: '고객 피드백 취합 및 개선 방안',
      session_id: 'mock-week-2',
      created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      query: '다음 분기 마케팅 전략 수립',
      session_id: 'mock-week-3',
      created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    },
    {
      query: '인력 채용 계획 및 일정 관리',
      session_id: 'mock-week-4',
      created_at: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString(),
    },

    // 이전 (12개)
    {
      query: '월간 보고서 작성 템플릿',
      session_id: 'mock-old-1',
      created_at: '2025-01-15T00:00:00.000Z',
    },
    {
      query: '연말 정산 자료 준비 체크리스트',
      session_id: 'mock-old-2',
      created_at: '2024-12-20T00:00:00.000Z',
    },
    {
      query: '파트너사 계약서 검토 포인트',
      session_id: 'mock-old-3',
      created_at: '2024-12-10T00:00:00.000Z',
    },
    {
      query: '제품 로드맵 업데이트 내용',
      session_id: 'mock-old-4',
      created_at: '2024-11-28T00:00:00.000Z',
    },
    {
      query: '사용자 데이터 분석 리포트',
      session_id: 'mock-old-5',
      created_at: '2024-11-15T00:00:00.000Z',
    },
    {
      query: '서비스 개선 사항 우선순위',
      session_id: 'mock-old-6',
      created_at: '2024-11-01T00:00:00.000Z',
    },
    {
      query: '해외 진출 전략 검토',
      session_id: 'mock-old-7',
      created_at: '2024-10-20T00:00:00.000Z',
    },
    {
      query: '브랜드 리뉴얼 프로젝트 계획',
      session_id: 'mock-old-8',
      created_at: '2024-10-05T00:00:00.000Z',
    },
    {
      query: '고객 만족도 조사 결과 분석',
      session_id: 'mock-old-9',
      created_at: '2024-09-25T00:00:00.000Z',
    },
    {
      query: '내부 교육 프로그램 기획',
      session_id: 'mock-old-10',
      created_at: '2024-09-10T00:00:00.000Z',
    },
    {
      query: '비용 절감 방안 모색',
      session_id: 'mock-old-11',
      created_at: '2024-08-28T00:00:00.000Z',
    },
    {
      query: '신규 서비스 론칭 일정',
      session_id: 'mock-old-12',
      created_at: '2024-08-15T00:00:00.000Z',
    },
  ],
};
