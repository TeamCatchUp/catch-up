// 경로: /search 페이지 → 필터바에서 Jira 버튼 클릭

import type { JiraNode } from '@/shared/types/query/jira';

export const JIRA_MOCK_DATA: JiraNode[] = [
  {
    id: 'PRJ-1',
    name: '서비스 고도화 프로젝트',
    type: 'project',
    is_public: false,
    last_edited: '3일전',
    children: [
      {
        id: 'BOARD-1',
        name: '프론트엔드 스프린트',
        type: 'board',
        is_public: false,
        last_edited: '1일전',
        children: [
          { id: 'JIRA-101', name: '로그인 페이지 UI 개선', type: 'ticket', is_public: false, last_edited: '2시간전' },
          { id: 'JIRA-102', name: '다크모드 버그 수정', type: 'ticket', is_public: false, last_edited: '5시간전' },
        ],
      },
      { id: 'JIRA-103', name: '백엔드 API 명세서 작성', type: 'ticket', is_public: false, last_edited: '2일전' },
    ],
  },
  {
    id: 'PRJ-2',
    name: '일본 진출 리서치',
    type: 'project',
    is_public: true,
    last_edited: '5일전',
    children: [],
  },
];
