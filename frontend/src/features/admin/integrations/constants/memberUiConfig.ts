import type { IntegrationService, MemberIntegrationStatus } from '../types/integrationModel';
import type { MemberSortKey } from '../types/memberDisplayModel';

/** 이용자 연동 표에서 노출할 서비스 컬럼 */
export const MEMBER_TABLE_SERVICES: IntegrationService[] = ['github', 'jira', 'slack'];

/** 이용자 연동 표 상태 칩 공통 클래스 */
export const MEMBER_LIST_STATUS_BADGE_BASE_CLASS =
  'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center justify-center gap-1 px-1.5 py-0.5';

/** 이용자 연동 표 상태 칩 색상 */
export const getMemberStatusBadgeClassName = (status: MemberIntegrationStatus) => {
  if (status === '완료') return 'bg-accent-green-neutral text-accent-green';
  if (status === '미등록') return 'bg-violet-5 text-violet-50';
  return 'bg-neutral-2 text-content-alternative';
};

/** 이용자 연동 표 정렬 옵션 */
export const SORT_OPTIONS: { key: MemberSortKey; label: string }[] = [
  { key: 'newest', label: '최신 순' },
  { key: 'oldest', label: '오래된 순' },
];
