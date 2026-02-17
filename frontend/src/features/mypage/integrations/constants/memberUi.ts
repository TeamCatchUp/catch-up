import type { IntegrationService, MemberIntegrationStatus } from '../types/integrations';
import type { MemberSortKey } from '../types/memberDisplay';

/** 이용자 연동 표에서 노출할 서비스 컬럼 */
export const MEMBER_TABLE_SERVICES: IntegrationService[] = ['github', 'jira', 'slack'];

/** 이용자 연동 표 상태 칩 공통 클래스 */
export const MEMBER_LIST_STATUS_BADGE_BASE_CLASS =
  'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center justify-center px-1.5 py-0.5';

/** 이용자 연동 표 상태 칩 색상 */
export const getMemberStatusBadgeClassName = (status: MemberIntegrationStatus) => {
  if (status === '완료') return 'bg-green-10 text-green-60';
  if (status === '미등록') return 'bg-pink-1 text-pink-40';
  return 'bg-neutral-2 text-gray-50';
};

/** 이용자 연동 표 정렬 옵션 */
export const SORT_OPTIONS: { key: MemberSortKey; label: string }[] = [
  { key: 'rank', label: '직급 순' },
  { key: 'newest', label: '최신 순' },
  { key: 'oldest', label: '오래된 순' },
];
