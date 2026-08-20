'use client';

import { useCallback, useMemo, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import type { WikiArtifactListItemDto, WikiChannelListItemDto } from '../api/wikiDto';
import { wikiQueries } from '../queries/wiki.queries';
import { buildWikiChannelAdmins, buildWikiFavorites, buildWikiNavTree } from '../utils/wikiNavTree';
import { useQueryErrorToast } from './useQueryErrorToast';

/** 트리 한 채널이 실을 문서 상한. 목록 API 최대치라 잘림이 가장 늦게 시작된다 */
const TREE_ARTIFACT_LIMIT = 200;

const EMPTY_CHANNELS: readonly WikiChannelListItemDto[] = [];

/**
 * 위키 SNB 데이터. 채널·즐겨찾기는 진입 시 받고,
 * 문서는 채널을 펼쳤을 때만 그 채널 몫을 한 번 받아온다.
 */
export function useWikiSideNav() {
  // 접어도 목록에서 빼지 않는다 — 다시 펼칠 때 왕복을 만들지 않기 위해서다
  const [openedChannelIds, setOpenedChannelIds] = useState<readonly string[]>([]);

  const channelsQuery = useQuery(wikiQueries.channels());
  const favoritesQuery = useQuery(wikiQueries.favorites());
  const channels = channelsQuery.data?.channels ?? EMPTY_CHANNELS;

  const tree = useQueries({
    queries: openedChannelIds.map((channelId) =>
      wikiQueries.artifacts({ channel_id: channelId, limit: TREE_ARTIFACT_LIMIT }),
    ),
    combine: (results) => ({
      documentsByChannel: new Map<string, readonly WikiArtifactListItemDto[]>(
        results.map((result, index) => [openedChannelIds[index], result.data?.items ?? []]),
      ),
      error: results.find((result) => result.error)?.error,
    }),
  });
  const { documentsByChannel } = tree;

  useQueryErrorToast(channelsQuery.error ?? favoritesQuery.error ?? tree.error);

  const treeNodes = useMemo(() => buildWikiNavTree(channels, documentsByChannel), [channels, documentsByChannel]);
  const channelAdmins = useMemo(() => buildWikiChannelAdmins(channels), [channels]);
  const favorites = useMemo(() => buildWikiFavorites(favoritesQuery.data?.items ?? []), [favoritesQuery.data]);

  /*
   * 채널 한 번의 요청이 그 채널의 폴더 문서까지 실어 오므로 폴더 펼침은 추가 요청이 없다.
   * NavTree는 자식이 있는 행에만 캐럿을 그려서, 폴더는 그 뒤에야 펼칠 수 있다.
   */
  const handleNodeToggle = useCallback(
    (nodeId: string, expanded: boolean) => {
      if (!expanded || !channels.some((channel) => channel.id === nodeId)) return;
      setOpenedChannelIds((prev) => (prev.includes(nodeId) ? prev : [...prev, nodeId]));
    },
    [channels],
  );

  return { treeNodes, favorites, channelAdmins, onNodeToggle: handleNodeToggle };
}
