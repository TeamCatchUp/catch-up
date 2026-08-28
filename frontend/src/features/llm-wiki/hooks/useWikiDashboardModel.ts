'use client';

import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { authQueries } from '@/shared/queries/auth.queries';

import { createWikiLocationIndex, mapWikiArtifactRows } from '../api/wikiMappers';
import {
  buildWikiArtifactParams,
  type DashboardQueryState,
  INITIAL_DASHBOARD_QUERY_STATE,
} from '../components/dashboard/dashboardFilters';
import type { ReviewQueueFilterOption } from '../components/review-queue/ReviewQueueFilterSearchPanel';
import { wikiQueries } from '../queries/wiki.queries';
import type { DocumentRowData, ReviewStatCardData } from '../types/llmWikiModel';
import { useQueryErrorToast } from './useQueryErrorToast';

/** 지표는 집계 API가 없어 목록의 total만 읽는다 — 한 줄만 받아 버린다. */
const STAT_LIMIT = 1;
const SEARCH_DEBOUNCE_MS = 300;

interface UseWikiDashboardModelReturn {
  queryState: DashboardQueryState;
  onQueryStateChange: (next: DashboardQueryState) => void;
  stats: readonly ReviewStatCardData[];
  documents: readonly DocumentRowData[];
  /** 첫 조회 전인지. 쪽 이동은 이전 쪽을 유지하므로 여기 서지 않는다 */
  documentsLoading: boolean;
  totalCount: number;
  assigneeOptions: readonly ReviewQueueFilterOption[];
  myUserId?: number;
}

/**
 * 대시보드 화면의 조회 상태와 데이터를 관리하는 페이지 모델 훅.
 * 문서 표는 서버가 거른 한 쪽을 그대로 그린다 — 담당자 다중 선택도 서버 파라미터다.
 */
export function useWikiDashboardModel(pageSize: number): UseWikiDashboardModelReturn {
  const [queryState, setQueryState] = useState<DashboardQueryState>(INITIAL_DASHBOARD_QUERY_STATE);
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [appliedPageSize, setAppliedPageSize] = useState(pageSize);

  // 쪽 크기가 바뀌면 offset 기준이 달라진다 — 어긋난 쪽으로 요청이 나가기 전에 1쪽으로 되돌린다.
  if (appliedPageSize !== pageSize) {
    setAppliedPageSize(pageSize);
    setQueryState((prev) => (prev.page === 1 ? prev : { ...prev, page: 1 }));
  }

  // 검색어 디바운스 — 타건마다 목록을 다시 부르지 않는다
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(queryState.keyword), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [queryState.keyword]);

  const listParams = useMemo(
    () => buildWikiArtifactParams({ ...queryState, keyword: debouncedKeyword }, pageSize),
    [debouncedKeyword, pageSize, queryState],
  );

  // placeholderData로 이전 쪽을 유지한다 — 로딩 시안이 없어 빈 표를 깜빡이지 않는 편을 택한다.
  const listQuery = useQuery({ ...wikiQueries.artifacts(listParams), placeholderData: keepPreviousData });
  const channelsQuery = useQuery(wikiQueries.channels());
  const membersQuery = useQuery(wikiQueries.members());
  const meQuery = useQuery(authQueries.me());

  const myUserId = meQuery.data?.user_id ?? undefined;

  const pendingReviewStat = useQuery(wikiQueries.artifacts({ status: 'pending_review', limit: STAT_LIMIT }));
  // 담당자를 모르는 동안에도 빈 배열을 실어 둔다 — undefined 프로퍼티는 캐시 키에서 탈락해 전체 지표와 겹친다
  const myAssignedStat = useQuery({
    ...wikiQueries.artifacts({ owner_user_id: myUserId === undefined ? [] : [myUserId], limit: STAT_LIMIT }),
    enabled: myUserId !== undefined,
  });
  const unassignedStat = useQuery(wikiQueries.artifacts({ unassigned: true, limit: STAT_LIMIT }));
  const allWikiStat = useQuery(wikiQueries.artifacts({ limit: STAT_LIMIT }));

  // 지표 4요청까지 한 신호로 합친다 — 화면 하나가 통째로 실패해도 토스트는 하나다
  useQueryErrorToast(
    listQuery.error ??
      channelsQuery.error ??
      membersQuery.error ??
      pendingReviewStat.error ??
      myAssignedStat.error ??
      unassignedStat.error ??
      allWikiStat.error,
  );

  // 문서 응답은 채널·폴더 id만 준다 — 경로 이름은 채널 목록과의 join 결과다.
  const locationIndex = useMemo(
    () => createWikiLocationIndex(channelsQuery.data?.channels ?? []),
    [channelsQuery.data],
  );

  const documents = useMemo(
    () => mapWikiArtifactRows(listQuery.data?.items ?? [], locationIndex),
    [listQuery.data, locationIndex],
  );

  const assigneeOptions = useMemo<readonly ReviewQueueFilterOption[]>(
    () =>
      (membersQuery.data?.items ?? []).map((member) => ({
        id: String(member.user_id),
        label: member.display_name,
      })),
    [membersQuery.data],
  );

  const stats = useMemo<readonly ReviewStatCardData[]>(
    () => [
      { id: 'stat-pending-review', label: '검토 대기', count: pendingReviewStat.data?.total ?? 0 },
      { id: 'stat-my-assigned', label: '내 담당', count: myAssignedStat.data?.total ?? 0 },
      { id: 'stat-unassigned', label: '담당자 미지정', count: unassignedStat.data?.total ?? 0 },
      { id: 'stat-all-wiki', label: '전체 위키', count: allWikiStat.data?.total ?? 0 },
    ],
    [allWikiStat.data, myAssignedStat.data, pendingReviewStat.data, unassignedStat.data],
  );

  return {
    queryState,
    onQueryStateChange: setQueryState,
    stats,
    documents,
    documentsLoading: listQuery.isPending,
    totalCount: listQuery.data?.total ?? 0,
    assigneeOptions,
    myUserId,
  };
}
