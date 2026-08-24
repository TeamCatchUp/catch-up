import { endOfDay, startOfDay } from 'date-fns';
import { describe, expect, it } from 'vitest';

import { REVIEW_STAT_CARD_FIXTURES } from '../../fixtures/llmWikiFixtures';
import {
  buildWikiArtifactParams,
  createAssigneeFilter,
  createCreatedAtFilter,
  createStatusFilter,
  DASHBOARD_SORT_OPTIONS,
  DASHBOARD_STATUS_OPTIONS,
  type DashboardActiveFilter,
  type DashboardQueryState,
  getFilterAxis,
  INITIAL_DASHBOARD_QUERY_STATE,
  resolveStatFilter,
} from './dashboardFilters';

const MY_USER_ID = 1;
const PAGE_SIZE = 20;

/** 카드를 누를 수 있는 지표만 필터를 갖는다 — 없으면 테스트가 죽은 카드를 잡는다. */
const filterOf = (statId: string) => resolveStatFilter(statId, MY_USER_ID)!.filter!;

const stateWith = (overrides: Partial<DashboardQueryState>): DashboardQueryState => ({
  ...INITIAL_DASHBOARD_QUERY_STATE,
  ...overrides,
});

const paramsOf = (filter: DashboardActiveFilter | null) => buildWikiArtifactParams(stateWith({ filter }), PAGE_SIZE);

describe('dashboardFilters', () => {
  it('시안의 지표 4종은 전부 누를 수 있다 — 하나라도 빠지면 그 카드가 죽은 카드가 된다', () => {
    expect(REVIEW_STAT_CARD_FIXTURES).toHaveLength(4);
    for (const stat of REVIEW_STAT_CARD_FIXTURES) {
      expect(resolveStatFilter(stat.id, MY_USER_ID), stat.id).toBeDefined();
    }
  });

  it('내 user_id가 없으면 "내 담당" 카드는 누를 수 없다 — 기준 없는 필터를 걸지 않는다', () => {
    expect(resolveStatFilter('stat-my-assigned')).toBeUndefined();
  });

  it('전체 위키는 필터가 아니라 해제다 — 누르면 표가 원래대로 돌아온다', () => {
    expect(resolveStatFilter('stat-all-wiki', MY_USER_ID)).toEqual({ filter: null });
  });

  it('모르는 지표는 필터가 없다 — 새 동작을 발명하지 않는다', () => {
    expect(resolveStatFilter('stat-not-yet-known', MY_USER_ID)).toBeUndefined();
  });

  it('검토 대기 카드는 상태 축을 켜고 status=pending_review로 나간다', () => {
    const filter = filterOf('stat-pending-review');

    expect(getFilterAxis(filter)).toBe('status');
    expect(paramsOf(filter)).toMatchObject({ status: 'pending_review' });
  });

  it('내 담당 카드는 담당자 축을 켜고 owner_user_id로 나간다', () => {
    const filter = filterOf('stat-my-assigned');

    expect(getFilterAxis(filter)).toBe('assignee');
    expect(paramsOf(filter)).toMatchObject({ owner_user_id: [MY_USER_ID] });
  });

  it('담당자 미지정은 unassigned=true로 나간다 — owner_user_id와 함께 실리면 서버가 422다', () => {
    const filter = filterOf('stat-unassigned');
    const params = paramsOf(filter);

    // 칩이 "담당자: 담당자 미지정"으로 겹쳐 적히지 않게 값 라벨은 축 이름을 뺀다.
    expect(filter.label).toBe('미지정');
    expect(getFilterAxis(filter)).toBe('assignee');
    expect(params).toMatchObject({ unassigned: true });
    expect(params).not.toHaveProperty('owner_user_id');
  });

  it('상태 필터의 라벨은 배지와 같은 공급원을 쓴다 — 두 곳에서 문구가 갈리지 않는다', () => {
    expect(DASHBOARD_STATUS_OPTIONS).toEqual(['pending_review', 'reviewed']);
    expect(createStatusFilter('pending_review').label).toBe('검토 대기');
    expect(createStatusFilter('reviewed').label).toBe('검토 완료');
  });

  it('검토 완료는 서버 파생 상태 published로 옮겨 나간다 — 이름이 갈리는 유일한 값이다', () => {
    expect(paramsOf(createStatusFilter('reviewed'))).toMatchObject({ status: 'published' });
    expect(paramsOf(createStatusFilter('pending_review'))).toMatchObject({ status: 'pending_review' });
  });

  it('담당자를 아무도 고르지 않으면 필터가 아니다 — 빈 선택으로 표를 비우지 않는다', () => {
    expect(createAssigneeFilter([])).toBeNull();
  });

  it('담당자 한 명은 서버가 거른다 — 표에서 다시 좁히지 않는다', () => {
    const filter = createAssigneeFilter([{ id: '2', label: '직원10' }])!;

    expect(paramsOf(filter)).toMatchObject({ owner_user_id: [2] });
  });

  it('담당자 2인 이상도 서버 파라미터로 나간다 — 고른 전원이 실린다', () => {
    const filter = createAssigneeFilter([
      { id: '2', label: '직원10' },
      { id: '3', label: '이진수' },
    ])!;

    expect(filter.label).toBe('직원10, 이진수');
    expect(paramsOf(filter)).toMatchObject({ owner_user_id: [2, 3] });
  });

  it('숫자가 아닌 담당자 id는 세지 않는다 — 서버 파라미터에 NaN이 실리면 안 된다', () => {
    const filter = createAssigneeFilter([{ id: 'not-a-user-id', label: '외부 협력자' }])!;

    expect(filter).toMatchObject({ kind: 'assignee', ownerUserIds: [] });
    expect(paramsOf(filter)).not.toHaveProperty('owner_user_id');
  });

  // 사용자가 고르는 것은 자기 시간대의 날짜다 — 경계도 로컬 시각으로 잘라야 시간대에 흔들리지 않는다.
  it('생성일 범위는 하루 단위로 자른다 — 끝날 늦게 만들어진 문서가 빠지면 안 된다', () => {
    const from = new Date(2024, 5, 1);
    const to = new Date(2024, 5, 30);
    const filter = createCreatedAtFilter({ from, to })!;

    expect(getFilterAxis(filter)).toBe('created-at');
    expect(filter.label).toBe('2024.06.01 - 2024.06.30');
    expect(paramsOf(filter)).toMatchObject({
      created_after: startOfDay(from).toISOString(),
      created_before: endOfDay(to).toISOString(),
    });
  });

  it('시작만 고른 범위는 그 하루로 본다 — 범위 선택 도중에도 필터가 성립한다', () => {
    const from = new Date(2024, 11, 1);
    const filter = createCreatedAtFilter({ from, to: undefined })!;

    expect(filter.label).toBe('2024.12.01');
    expect(paramsOf(filter)).toMatchObject({
      created_after: startOfDay(from).toISOString(),
      created_before: endOfDay(from).toISOString(),
    });
  });

  it('범위가 없으면 필터가 아니다', () => {
    expect(createCreatedAtFilter(undefined)).toBeNull();
    expect(createCreatedAtFilter({ from: undefined, to: undefined })).toBeNull();
  });

  it('정렬 옵션은 최근 변경 순·오래된순 2개다', () => {
    expect(DASHBOARD_SORT_OPTIONS.map((option) => option.label)).toEqual(['최근 변경 순', '오래된순']);
  });

  it('정렬 2종은 같은 키의 방향 차이다 — 최근 활동 순서를 서버가 만든다', () => {
    expect(buildWikiArtifactParams(stateWith({ sortId: 'recent' }), PAGE_SIZE)).toMatchObject({
      sort: 'last_activity',
      order: 'desc',
    });
    expect(buildWikiArtifactParams(stateWith({ sortId: 'oldest' }), PAGE_SIZE)).toMatchObject({
      sort: 'last_activity',
      order: 'asc',
    });
  });

  it('쪽 번호는 offset으로 나간다 — 첫 쪽은 0이다', () => {
    expect(buildWikiArtifactParams(stateWith({ page: 1 }), PAGE_SIZE)).toMatchObject({ limit: 20, offset: 0 });
    expect(buildWikiArtifactParams(stateWith({ page: 3 }), PAGE_SIZE)).toMatchObject({ limit: 20, offset: 40 });
  });

  it('검색어는 다듬어 q로 나가고, 공백뿐이면 실리지 않는다', () => {
    expect(buildWikiArtifactParams(stateWith({ keyword: '  재시도 정책 ' }), PAGE_SIZE)).toMatchObject({
      q: '재시도 정책',
    });
    expect(buildWikiArtifactParams(stateWith({ keyword: '   ' }), PAGE_SIZE)).not.toHaveProperty('q');
  });

  it('필터가 없으면 정렬·쪽 파라미터만 나간다 — 빈 필터 키를 만들지 않는다', () => {
    expect(Object.keys(buildWikiArtifactParams(INITIAL_DASHBOARD_QUERY_STATE, PAGE_SIZE)).sort()).toEqual([
      'limit',
      'offset',
      'order',
      'sort',
    ]);
  });

  it('담당자 축의 좁히기는 전부 서버 몫이다 — 미지정도 owner_user_id를 실어 보내지 않는다', () => {
    expect(paramsOf({ kind: 'unassigned', label: '미지정' })).not.toHaveProperty('owner_user_id');
  });
});
