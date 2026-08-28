'use client';

import { useEffect, useMemo } from 'react';
import { useInfiniteQuery,type UseInfiniteQueryResult } from '@tanstack/react-query';

import type { AccountOption } from '../components/user-mapping/AccountSelectDropdown';
import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type { VendorUsersResponse } from '../types/integrationApi';
import type { IntegrationService } from '../types/integrationModel';

const toOptions = (pages: VendorUsersResponse[] | undefined): AccountOption[] =>
  pages?.flatMap((page) =>
    page.items.map((item) => ({
      id: item.id,
      name: item.name,
      identifier: item.identifier ?? '',
      picture: item.picture,
    })),
  ) ?? [];

/**
 * 백엔드가 페이지네이션을 강제한다(size 최대 100) — 드롭다운은 후보 전체가 필요하므로
 * 다음 페이지가 남아 있는 동안 순차로 끝까지 당긴다. 이게 없으면 51번째 이후 계정은
 * 선택할 수 없고 클라이언트 검색에도 잡히지 않는다.
 */
const useDrainAllPages = (query: UseInfiniteQueryResult<unknown, unknown>) => {
  const { hasNextPage, isFetchingNextPage, isError, fetchNextPage } = query;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage && !isError) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, isError, fetchNextPage]);
};

/**
 * 수정 모드의 계정 후보 목록 — vendor 4종을 병렬 조회해 서비스별 드롭다운 옵션으로 변환.
 * `useUserMappingEdit`에서 추출했다. `enabled=false`면 조회하지 않고 빈 결과를 준다.
 */
export function useVendorAccountOptions(enabled: boolean) {
  const githubUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'github' }),
    enabled,
  });
  const atlassianUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'atlassian' }),
    enabled,
  });
  const slackUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'slack' }),
    enabled,
  });
  const channelTalkUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'channel_talk' }),
    enabled,
  });

  useDrainAllPages(githubUsers);
  useDrainAllPages(atlassianUsers);
  useDrainAllPages(slackUsers);
  useDrainAllPages(channelTalkUsers);

  return useMemo<Partial<Record<IntegrationService, AccountOption[]>>>(() => {
    if (!enabled) return {};
    return {
      github: toOptions(githubUsers.data?.pages),
      jira: toOptions(atlassianUsers.data?.pages),
      slack: toOptions(slackUsers.data?.pages),
      channel_talk: toOptions(channelTalkUsers.data?.pages),
    };
  }, [
    enabled,
    githubUsers.data?.pages,
    atlassianUsers.data?.pages,
    slackUsers.data?.pages,
    channelTalkUsers.data?.pages,
  ]);
}
