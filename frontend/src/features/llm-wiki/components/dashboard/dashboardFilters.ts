import type { DateRange } from 'react-day-picker';
import { endOfDay, format, startOfDay } from 'date-fns';

import type { WikiArtifactListParams, WikiArtifactStatusDto } from '../../api/wikiDto';
import type { KnownDocumentStatus } from '../../types/llmWikiModel';
import { getDocumentStatusLabel } from '../document/DocumentStatusBadge';
import type { DashboardFilterId } from './DashboardFilterBar';

/** 담당자 선택 하나. 검토 큐 필터 패널의 옵션과 같은 모양이고 id는 user_id 문자열이다. */
interface DashboardAssigneeSelection {
  id: string;
  label: string;
}

/** 문서 표에 걸린 필터 하나. 칩은 "축: 값"으로 적히고 값은 목록 API 파라미터가 된다. */
export type DashboardActiveFilter =
  | { kind: 'status'; label: string; status: KnownDocumentStatus }
  | { kind: 'assignee'; label: string; ownerUserIds: readonly number[] }
  | { kind: 'unassigned'; label: string }
  | { kind: 'created-at'; label: string; createdAfter: string; createdBefore: string };

/** 미지정은 담당자 축의 한 값이라 칩 자리를 담당자와 나눠 쓴다. */
const AXIS_BY_KIND: Readonly<Record<DashboardActiveFilter['kind'], DashboardFilterId>> = {
  status: 'status',
  assignee: 'assignee',
  unassigned: 'assignee',
  'created-at': 'created-at',
};

export function getFilterAxis(filter: DashboardActiveFilter): DashboardFilterId {
  return AXIS_BY_KIND[filter.kind];
}

/** 정렬 옵션. 시안 드롭다운은 2개다(사용자 확정). */
export type DashboardSortId = 'recent' | 'oldest';

export const DASHBOARD_SORT_OPTIONS: readonly { id: DashboardSortId; label: string }[] = [
  { id: 'recent', label: '최근 변경 순' },
  { id: 'oldest', label: '오래된순' },
];

export function getSortLabel(sortId: DashboardSortId): string {
  return DASHBOARD_SORT_OPTIONS.find((option) => option.id === sortId)!.label;
}

/** 상태 드롭다운 옵션. 시안이 검토 대기·검토 완료 2종만 두고 "하나만 선택"으로 못박았다. */
export const DASHBOARD_STATUS_OPTIONS: readonly KnownDocumentStatus[] = ['pending_review', 'reviewed'];

/** 문서 표의 조회 상태. 서버 파라미터의 재료이자 필터 UI의 표시 상태다. */
export interface DashboardQueryState {
  filter: DashboardActiveFilter | null;
  /** 담당자 패널의 선택 표시용 id */
  selectedAssigneeIds: readonly string[];
  createdAtRange?: DateRange;
  keyword: string;
  sortId: DashboardSortId;
  /** 1부터 센다 */
  page: number;
}

export const INITIAL_DASHBOARD_QUERY_STATE: DashboardQueryState = {
  filter: null,
  selectedAssigneeIds: [],
  keyword: '',
  sortId: 'recent',
  page: 1,
};

/** 필터가 아니라 해제인 지표. "전체 위키"를 누르면 표가 원래대로 돌아온다. */
const CLEAR_FILTER_STAT_ID = 'stat-all-wiki';

/**
 * 지표 카드를 눌렀을 때 걸 필터.
 * `undefined`는 누를 수 없는 카드고, `{ filter: null }`은 해제다 — 둘을 구분해야 죽은 카드가 생기지 않는다.
 */
export function resolveStatFilter(
  statId: string,
  myUserId?: number,
): { filter: DashboardActiveFilter | null } | undefined {
  if (statId === CLEAR_FILTER_STAT_ID) return { filter: null };
  if (statId === 'stat-pending-review') return { filter: createStatusFilter('pending_review') };
  // 카드 라벨은 "담당자 미지정"이지만 칩은 축 이름을 앞에 달아서 "담당자: 미지정"으로 줄인다.
  if (statId === 'stat-unassigned') return { filter: { kind: 'unassigned', label: '미지정' } };
  // 내 담당은 내 user_id가 있어야 성립한다 — 없으면 누를 수 없는 카드다.
  if (statId === 'stat-my-assigned' && myUserId !== undefined) {
    return { filter: { kind: 'assignee', label: '내 담당', ownerUserIds: [myUserId] } };
  }

  return undefined;
}

/** 상태 드롭다운 선택 → 필터. 라벨은 배지와 같은 공급원을 쓴다. */
export function createStatusFilter(status: KnownDocumentStatus): DashboardActiveFilter {
  return { kind: 'status', label: getDocumentStatusLabel(status) ?? status, status };
}

/**
 * 담당자 다중 선택 → 필터. 숫자가 아닌 id는 담당자로 세지 않는다.
 * 아무도 고르지 않았으면 필터가 아니다 — 빈 선택으로 표를 비우지 않는다.
 */
export function createAssigneeFilter(
  selected: readonly DashboardAssigneeSelection[],
): DashboardActiveFilter | null {
  if (selected.length === 0) return null;

  return {
    kind: 'assignee',
    label: selected.map((option) => option.label).join(', '),
    ownerUserIds: selected.map((option) => Number(option.id)).filter((id) => Number.isInteger(id)),
  };
}

/**
 * 생성일 범위 → 필터. 하루 단위로 자른다 — 사용자가 고르는 것은 날짜이지 시각이 아니다.
 * 시작만 고른 상태(범위 선택 도중)는 그 하루로 본다.
 */
export function createCreatedAtFilter(range: DateRange | undefined): DashboardActiveFilter | null {
  if (!range?.from) return null;

  const label = range.to
    ? `${format(range.from, 'yyyy.MM.dd')} - ${format(range.to, 'yyyy.MM.dd')}`
    : format(range.from, 'yyyy.MM.dd');

  return {
    kind: 'created-at',
    label,
    createdAfter: startOfDay(range.from).toISOString(),
    createdBefore: endOfDay(range.to ?? range.from).toISOString(),
  };
}

/** 화면 상태 → 서버 파생 상태. reviewed만 이름이 갈린다. */
function toArtifactStatusParam(status: KnownDocumentStatus): WikiArtifactStatusDto {
  return status === 'reviewed' ? 'published' : 'pending_review';
}

/**
 * 조회 상태 → 문서 목록 파라미터. 정렬 2종은 둘 다 최근 활동 키이고 방향만 갈린다.
 * 담당자 조건은 owner_user_id·unassigned 중 하나만 실린다(둘 다 주면 서버가 422다).
 */
export function buildWikiArtifactParams(state: DashboardQueryState, pageSize: number): WikiArtifactListParams {
  const keyword = state.keyword.trim();
  const common = {
    sort: 'last_activity',
    order: state.sortId === 'recent' ? 'desc' : 'asc',
    limit: pageSize,
    offset: (state.page - 1) * pageSize,
    ...(keyword ? { q: keyword } : {}),
  } satisfies WikiArtifactListParams;

  const filter = state.filter;
  if (!filter) return common;

  switch (filter.kind) {
    case 'status':
      return { ...common, status: toArtifactStatusParam(filter.status) };
    case 'unassigned':
      return { ...common, unassigned: true };
    case 'created-at':
      return { ...common, created_after: filter.createdAfter, created_before: filter.createdBefore };
    case 'assignee':
      // 서버가 여러 담당자를 받아 그중 한 명이라도 담당인 문서를 돌려준다 — 화면은 다시 거르지 않는다.
      return filter.ownerUserIds.length > 0 ? { ...common, owner_user_id: [...filter.ownerUserIds] } : common;
  }
}
