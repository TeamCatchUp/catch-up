import { JiraTicketList } from '@/components/UI/JiraTicketList';
import { ReacentlySearchList } from '@/components/UI/RecetlySearchList';
import { RECENT_SEARCH_DATA } from '@/constants/RecentlySearchData';

const JIRA_DATA = [
  { id: 'JIRA-101', label: '일본 시장 진출 리서치 범위 및 방향 정의' },
  { id: 'JIRA-102', label: '일본 진출 가설 검증 결과 정리' },
  { id: 'JIRA-103', label: '신규 기능 인터페이스 설계' },
  { id: 'JIRA-104', label: '백엔드 API 최적화 작업' },
];

export const DefaultSearchContent = () => {
  return (
    <>
      <ReacentlySearchList title="최근 질문" querys={RECENT_SEARCH_DATA} />
      <JiraTicketList tickets={JIRA_DATA} title="최근 확인한 지라 티켓" />
    </>
  );
};
