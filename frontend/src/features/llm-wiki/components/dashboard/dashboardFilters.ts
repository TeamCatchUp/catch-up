import type { DocumentRowData, KnownDocumentStatus } from '../../types/llmWikiModel';
import { getDocumentStatusLabel } from '../document/DocumentStatusBadge';
import type { DashboardFilterId } from './DashboardFilterBar';

/** 문서 표에 걸린 필터 하나. 칩은 "축: 값"으로 표기하고 표는 matches로 좁힌다. */
export interface DashboardActiveFilter {
  axis: DashboardFilterId;
  /** 칩의 값 자리에 들어갈 라벨 */
  label: string;
  matches: (row: DocumentRowData, currentUserName: string) => boolean;
}

/** 상태 드롭다운 옵션. 시안이 검토 대기·검토 완료 2종만 두고 "하나만 선택"으로 못박았다. */
export const DASHBOARD_STATUS_OPTIONS: readonly KnownDocumentStatus[] = ['pending_review', 'reviewed'];

/** 지표 카드 → 필터. 시안에 있는 것만 매핑하고 모르는 id는 필터를 만들지 않는다(카드가 클릭 불가로 렌더된다). */
const STAT_FILTERS: Readonly<Record<string, DashboardActiveFilter>> = {
  'stat-pending-review': {
    axis: 'status',
    label: '검토 대기',
    matches: (row) => row.status === 'pending_review',
  },
  'stat-my-assigned': {
    axis: 'assignee',
    label: '내 담당',
    matches: (row, currentUserName) => row.ownerName === currentUserName,
  },
  'stat-unassigned': {
    // 카드 라벨은 "담당자 미지정"이지만 칩은 축 이름을 앞에 달아서 "담당자: 미지정"으로 줄인다.
    axis: 'assignee',
    label: '미지정',
    matches: (row) => row.ownerName === null,
  },
};

/** 필터가 아니라 해제인 지표. "전체 위키"를 누르면 표가 원래대로 돌아온다. */
const CLEAR_FILTER_STAT_ID = 'stat-all-wiki';

/**
 * 지표 카드를 눌렀을 때 걸 필터.
 * `undefined`는 누를 수 없는 카드고, `{ filter: null }`은 해제다 — 둘을 구분해야 죽은 카드가 생기지 않는다.
 */
export function resolveStatFilter(statId: string): { filter: DashboardActiveFilter | null } | undefined {
  if (statId === CLEAR_FILTER_STAT_ID) return { filter: null };

  const filter = STAT_FILTERS[statId];
  return filter ? { filter } : undefined;
}

/** 상태 드롭다운 선택 → 필터. 라벨은 배지와 같은 공급원을 쓴다. */
export function createStatusFilter(status: KnownDocumentStatus): DashboardActiveFilter {
  return {
    axis: 'status',
    label: getDocumentStatusLabel(status) ?? status,
    matches: (row) => row.status === status,
  };
}

/**
 * 담당자 다중 선택 → 필터. 고른 사람 중 하나가 담당인 행만 남긴다.
 * 아무도 고르지 않았으면 필터가 아니다 — 빈 배열로 표를 비우지 않는다.
 */
export function createAssigneeFilter(names: readonly string[]): DashboardActiveFilter | null {
  if (names.length === 0) return null;

  return {
    axis: 'assignee',
    label: names.join(', '),
    matches: (row) => row.ownerName !== null && names.includes(row.ownerName),
  };
}

/** 필터가 없으면 원본을 그대로 돌려준다 — 표는 항상 같은 배열 계약을 받는다. */
export function filterDocuments(
  documents: readonly DocumentRowData[],
  filter: DashboardActiveFilter | null,
  currentUserName: string,
): readonly DocumentRowData[] {
  if (!filter) return documents;
  return documents.filter((row) => filter.matches(row, currentUserName));
}
