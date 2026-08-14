import { describe, expect, it } from 'vitest';

import { createDocumentRow, DOCUMENT_ROW_FIXTURES, REVIEW_STAT_CARD_FIXTURES } from '../../fixtures/llmWikiFixtures';
import {
  createAssigneeFilter,
  createStatusFilter,
  DASHBOARD_STATUS_OPTIONS,
  filterDocuments,
  findStatFilter,
} from './dashboardFilters';

const CURRENT_USER = '팀원F';

describe('dashboardFilters', () => {
  it('시안의 지표 3종에 전부 필터가 걸린다 — 하나라도 빠지면 그 카드가 죽은 카드가 된다', () => {
    for (const stat of REVIEW_STAT_CARD_FIXTURES) {
      expect(findStatFilter(stat.id), stat.id).toBeDefined();
    }
  });

  it('모르는 지표는 필터가 없다 — 새 동작을 발명하지 않는다', () => {
    expect(findStatFilter('stat-not-yet-known')).toBeUndefined();
  });

  it('검토 대기 카드는 상태 축을 켜고 pending_review만 남긴다', () => {
    const filter = findStatFilter('stat-pending-review')!;
    expect(filter.axis).toBe('status');

    const result = filterDocuments(DOCUMENT_ROW_FIXTURES, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThan(DOCUMENT_ROW_FIXTURES.length);
    expect(result.every((row) => row.status === 'pending_review')).toBe(true);
  });

  it('내 담당 카드는 담당자 축을 켜고 현재 사용자 행만 남긴다', () => {
    const filter = findStatFilter('stat-my-assigned')!;
    expect(filter.axis).toBe('assignee');

    const result = filterDocuments(DOCUMENT_ROW_FIXTURES, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((row) => row.ownerName === CURRENT_USER)).toBe(true);
  });

  it('담당자 미지정은 ownerName이 null인 행만 남긴다 — 빈 문자열 담당자와 섞이지 않는다', () => {
    const filter = findStatFilter('stat-unassigned')!;
    // 칩이 "담당자: 담당자 미지정"으로 겹쳐 적히지 않게 값 라벨은 축 이름을 뺀다.
    expect(filter.label).toBe('미지정');
    const documents = [...DOCUMENT_ROW_FIXTURES, createDocumentRow({ id: 'doc-blank-owner', ownerName: '' })];

    const result = filterDocuments(documents, filter, CURRENT_USER);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((row) => row.ownerName === null)).toBe(true);
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
    expect(result.every((row) => row.ownerName === '직원10' || row.ownerName === '이진수')).toBe(true);
    // 미지정 행이 섞이면 "고른 사람"의 뜻이 무너진다
    expect(result.some((row) => row.ownerName === null)).toBe(false);
  });

  it('필터가 없으면 원본을 그대로 돌려준다', () => {
    expect(filterDocuments(DOCUMENT_ROW_FIXTURES, null, CURRENT_USER)).toBe(DOCUMENT_ROW_FIXTURES);
  });
});
