'use client';

import { useQuery } from '@tanstack/react-query';

import WikiSideNav, {
  type SnbMenuActionId,
  type WikiTreeNode,
} from '@/shared/components/layout/sideNavBar/WikiSideNav';
import { authQueries } from '@/shared/queries/auth.queries';

import { useWikiSideNav } from '../../hooks/useWikiSideNav';
import { useRenameWikiChannelMutation, useRenameWikiFolderMutation } from '../../queries/wikiChannels.mutations';
import { useWikiFavoriteToggleMutation } from '../../queries/wikiFavorites.mutations';

/** 위키 SNB에 실 데이터를 물리는 자리. shared 층은 features를 import할 수 없어 여기서 잇는다. */
export default function WikiSideNavContainer() {
  const { treeNodes, favorites, channelAdmins, onNodeToggle } = useWikiSideNav();
  const { data: me } = useQuery(authQueries.me());
  const favoriteToggle = useWikiFavoriteToggleMutation();
  const renameChannel = useRenameWikiChannelMutation();
  const renameFolder = useRenameWikiFolderMutation();

  // 즐겨찾기 항목은 문서 행에만 뜬다 — 그 노드 id가 곧 artifact_id다
  const handleMenuAction = (nodeId: string | undefined, actionId: SnbMenuActionId) => {
    if (nodeId === undefined || (actionId !== 'favorite' && actionId !== 'unfavorite')) return;
    favoriteToggle.mutate({ artifactId: nodeId, favorite: actionId === 'favorite' });
  };

  // 문서는 이름 변경 API가 없어 채널·폴더만 여기로 온다
  const handleRenameSubmit = (node: WikiTreeNode, name: string) => {
    if (node.kind === 'channel') renameChannel.mutate({ channelId: node.id, name });
    else if (node.kind === 'folder') renameFolder.mutate({ channelId: node.channelId, folderId: node.id, name });
  };

  return (
    <WikiSideNav
      canCreateWiki={me?.role === 'admin'}
      treeNodes={treeNodes}
      favorites={favorites}
      channelAdmins={channelAdmins}
      onNodeToggle={onNodeToggle}
      onMenuAction={handleMenuAction}
      onRenameSubmit={handleRenameSubmit}
    />
  );
}
