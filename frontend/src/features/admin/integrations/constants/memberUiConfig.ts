import type { IntegrationService, MemberIntegrationStatus } from '../types/integrationModel';
import type { MemberSortKey } from '../types/memberDisplayModel';

/** 이용자 연동 표에서 노출할 서비스 컬럼 (Atlassian/Github/Slack/채널톡 순서) */
export const MEMBER_TABLE_SERVICES: IntegrationService[] = ['jira', 'github', 'slack', 'channel_talk'];

/** 이용자 연동 표 상태 칩 공통 클래스 */
export const MEMBER_LIST_STATUS_BADGE_BASE_CLASS =
  'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center justify-center gap-1 px-1.5 py-0.5';

/** 이용자 연동 표 상태 칩 색상 */
export const getMemberStatusBadgeClassName = (status: MemberIntegrationStatus) => {
  if (status === '완료') return 'bg-accent-green-neutral text-accent-green-default';
  if (status === '미등록') return 'bg-accent-violet-neutral text-accent-violet-default';
  return 'bg-neutral-2 text-text-normal-alternative';
};

/** 이용자 연동 표 정렬 옵션 */
export const SORT_OPTIONS: { key: MemberSortKey; label: string }[] = [
  { key: 'newest', label: '최신 순' },
  { key: 'oldest', label: '오래된 순' },
];

// ─── UsersTable className 상수 ───

/** UsersTable 컬럼 헤더 라벨 (모든 IntegrationService 정의 — over-coverage 안전) */
export const SERVICE_HEADER_LABELS: Record<IntegrationService, string> = {
  github: 'Github',
  jira: 'Atlassian',
  slack: 'Slack',
  confluence: 'Confluence',
  channel_talk: '채널톡',
};

export const TABLE_HEADER_ROW_CLASS =
  'border-line-normal-normal flex h-9 shrink-0 items-center gap-4 border-y py-1 pr-6 pl-12 transition-colors';
export const TABLE_BODY_ROW_CLASS =
  'border-line-normal-neutral bg-fill-normal-normal flex h-16.5 items-center justify-center gap-4 border-b px-6 py-3 transition-colors';
export const KEYCLOAK_COLUMN_CLASS = 'flex min-w-px flex-[1_0_0] items-center';
export const SERVICES_GROUP_CLASS = 'flex min-w-px flex-[1_0_0] items-center';
/** 헤더/계정 정보 셀 공통: 1열 column flex + truncate */
export const FLEX_COLUMN_CELL_CLASS = 'flex min-w-px flex-[1_0_0] flex-col justify-center overflow-hidden';
export const BODY_SERVICE_COLUMN_CLASS = 'flex min-w-px max-w-41.25 flex-[1_0_0]';
export const KEYCLOAK_USER_CELL_CLASS = 'relative justify-center gap-3';
export const SERVICE_ACCOUNT_IDENTIFIER_CLASS = 'flex h-5 w-full shrink-0 flex-col justify-center overflow-hidden';

/** 서비스 컬럼 그룹 className — services 1개(채널톡 단독)면 gap 제거, 다중이면 gap-14. */
export const getServicesGroupClass = (isSingleService: boolean): string =>
  `${SERVICES_GROUP_CLASS} ${isSingleService ? 'gap-0' : 'gap-14'}`;

/** Keycloak 컬럼 className — 다중 서비스일 때 max-w-35 캡 적용. */
export const getKeycloakColumnClass = (isSingleService: boolean): string =>
  `${KEYCLOAK_COLUMN_CLASS}${!isSingleService ? ' max-w-35' : ''}`;
