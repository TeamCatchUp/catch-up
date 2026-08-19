import { describe, expect, it } from 'vitest';

import { createDocumentRow, DOCUMENT_ROW_FIXTURES, REVIEW_STAT_CARD_FIXTURES } from '../../fixtures/llmWikiFixtures';
import {
  createAssigneeFilter,
  createCreatedAtFilter,
  createStatusFilter,
  DASHBOARD_SORT_OPTIONS,
  DASHBOARD_STATUS_OPTIONS,
  filterDocuments,
  resolveStatFilter,
  sortDocuments,
} from './dashboardFilters';

const CURRENT_USER = '팀원F';

/** 카드를 누를 수 있는 지표만 필터를 갖는다 — 없으면 테스트가 죽은 카드를 잡는다. */
const filterOf = (statId: string) => resolveStatFilter(statId)!.filter!;

describe('dashboardFilters', () => {
  it('시안의 지표 4종은 전부 누를 수 있다 — 하나라도 빠지면 그 카드가 죽은 카드가 된다', () => {
    expect(REVIEW_STAT_CARD_FIXTURES).toHaveLength(4);
    for (const stat of REVIEW_STAT_CARD_FIXTURES) {
      expect(resolveStatFilter(stat.id), stat.id).toBeDefined();
    }
  });

  it('전체 위키는 필터가 아니라 해제다 — 누르면 표가 원래대로 돌아온다', () => {
    expect(resolveStatFilter('stat-all-wiki')).toEqual({ filter: null });
  });

  it('모르는 지표는 필터가 없다 — 새 동작을 발명하지 않는다', () => {
    expect(resolveStatFilter('stat-not-yet-known')).toBeUndefined();
  });

  it('검토 대기 카드는 상태 축을 켜고 pending_review만 남긴다', () => {
    const filter = filterOf('stat-pending-review');
    expect(filter.axis).toBe('status');

    const result = filterDocuments(DOCUMENT_ROW_FIXTURES, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThan(DOCUMENT_ROW_FIXTURES.length);
    expect(result.every((row) => row.status === 'pending_review')).toBe(true);
  });

  it('내 담당 카드는 담당자 축을 켜고 현재 사용자 행만 남긴다', () => {
    const filter = filterOf('stat-my-assigned');
    expect(filter.axis).toBe('assignee');

    const result = filterDocuments(DOCUMENT_ROW_FIXTURES, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((row) => row.owners.some((owner) => owner.displayName === CURRENT_USER))).toBe(true);
  });

  it('담당자 미지정은 owners가 빈 배열인 행만 남긴다 — 빈 문자열 담당자와 섞이지 않는다', () => {
    const filter = filterOf('stat-unassigned');
    // 칩이 "담당자: 담당자 미지정"으로 겹쳐 적히지 않게 값 라벨은 축 이름을 뺀다.
    expect(filter.label).toBe('미지정');
    const documents = [
      ...DOCUMENT_ROW_FIXTURES,
      createDocumentRow({ id: 'doc-blank-owner', owners: [{ userId: 99, displayName: '', profileImageUrl: null }] }),
    ];

    const result = filterDocuments(documents, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((row) => row.owners.length === 0)).toBe(true);
    expect(result.some((row) => row.id === 'doc-blank-owner')).toBe(false);
  });

  it('상태 필터의 라벨은 배지와 같은 공급원을 쓴다 — 두 곳에서 문구가 갈리지 않는다', () => {
    expect(DASHBOARD_STATUS_OPTIONS).toEqual(['pending_review', 'reviewed']);
    expect(createStatusFilter('pending_review').label).toBe('검토 대기');
    expect(createStatusFilter('reviewed').label).toBe('검토 완료');
  });

  it('담당자를 아무도 고르지 않으면 필터가 아니다 — 빈 선택으로 표를 비우지 않는다', () => {
    expect(createAssigneeFilter([])).toBeNull();
  });

  it('담당자 다중 선택은 고른 사람 중 하나가 담당인 행을 남긴다', () => {
    const filter = createAssigneeFilter(['직원10', '이진수'])!;
    expect(filter.axis).toBe('assignee');

    const result = filterDocuments(DOCUMENT_ROW_FIXTURES, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(
      result.every((row) =>
        row.owners.some((owner) => owner.displayName === '직원10' || owner.displayName === '이진수'),
      ),
    ).toBe(true);
    // 미지정 행이 섞이면 "고른 사람"의 뜻이 무너진다
    expect(result.some((row) => row.owners.length === 0)).toBe(false);
  });

  it('필터가 없으면 원본을 그대로 돌려준다', () => {
    expect(filterDocuments(DOCUMENT_ROW_FIXTURES, null, CURRENT_USER)).toBe(DOCUMENT_ROW_FIXTURES);
  });

  // 사용자가 고르는 것은 자기 시간대의 날짜다 — 경계 표본도 로컬 시각으로 만들어야 시간대에 흔들리지 않는다.
  const localIso = (year: number, monthIndex: number, day: number, hour = 0, minute = 0) =>
    new Date(year, monthIndex, day, hour, minute).toISOString();

  it('생성일 범위는 하루 단위로 자른다 — 끝날 당일 늦게 만들어진 문서가 빠지면 안 된다', () => {
    const boundary = createDocumentRow({ id: 'doc-boundary', createdAt: localIso(2024, 5, 30, 23, 30) });
    const filter = createCreatedAtFilter({ from: new Date(2024, 5, 1), to: new Date(2024, 5, 30) })!;

    expect(filter.axis).toBe('created-at');
    expect(filter.label).toBe('2024.06.01 - 2024.06.30');
    expect(filter.matches(boundary, CURRENT_USER)).toBe(true);
  });

  it('시작만 고른 범위는 그 하루로 본다 — 범위 선택 도중에도 필터가 성립한다', () => {
    const filter = createCreatedAtFilter({ from: new Date(2024, 11, 1), to: undefined })!;

    expect(filter.label).toBe('2024.12.01');
    expect(filter.matches(createDocumentRow({ createdAt: localIso(2024, 11, 1, 12) }), CURRENT_USER)).toBe(true);
    expect(filter.matches(createDocumentRow({ createdAt: localIso(2024, 11, 2, 0, 30) }), CURRENT_USER)).toBe(false);
  });

  it('범위가 없으면 필터가 아니다', () => {
    expect(createCreatedAtFilter(undefined)).toBeNull();
    expect(createCreatedAtFilter({ from: undefined, to: undefined })).toBeNull();
  });

  it('정렬 옵션은 최근 변경 순·오래된순 2개다', () => {
    expect(DASHBOARD_SORT_OPTIONS.map((option) => option.label)).toEqual(['최근 변경 순', '오래된순']);
  });

  it('정렬은 최근 활동 ISO로 비교한다 — 표시 문자열("3시간 전")로는 순서를 만들 수 없다', () => {
    const recent = sortDocuments(DOCUMENT_ROW_FIXTURES, 'recent');
    const oldest = sortDocuments(DOCUMENT_ROW_FIXTURES, 'oldest');

    expect(recent[0].lastActivityAt >= recent[recent.length - 1].lastActivityAt).toBe(true);
    expect(oldest[0].lastActivityAt <= oldest[oldest.length - 1].lastActivityAt).toBe(true);
    expect(recent.map((row) => row.id)).toEqual([...oldest].reverse().map((row) => row.id));
  });

  it('정렬은 원본 배열을 건드리지 않는다', () => {
    const before = DOCUMENT_ROW_FIXTURES.map((row) => row.id);
    sortDocuments(DOCUMENT_ROW_FIXTURES, 'oldest');

    expect(DOCUMENT_ROW_FIXTURES.map((row) => row.id)).toEqual(before);
  });
});
