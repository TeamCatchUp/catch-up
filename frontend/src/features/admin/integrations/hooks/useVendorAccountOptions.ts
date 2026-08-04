'use client';

import { useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';

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
