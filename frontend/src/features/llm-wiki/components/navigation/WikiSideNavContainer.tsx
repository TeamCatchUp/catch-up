'use client';

import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import WikiSideNav, {
  findTreeNode,
  SNB_POPOVER_SHELL_CLASS,
  type SnbMenuActionId,
  type WikiTreeNode,
} from '@/shared/components/layout/sideNavBar/WikiSideNav';
import { buttonVariants } from '@/shared/components/ui/button';
import { Popover, PopoverAnchor, PopoverContent } from '@/shared/components/ui/popover';
import { toast } from '@/shared/components/ui/toast';
import { authQueries } from '@/shared/queries/auth.queries';

import { useWikiSideNav } from '../../hooks/useWikiSideNav';
import { wikiQueries } from '../../queries/wiki.queries';
import { useMoveWikiArtifactMutation } from '../../queries/wikiArtifacts.mutations';
import {
  useCreateWikiFolderMutation,
  useRenameWikiChannelMutation,
  useRenameWikiFolderMutation,
} from '../../queries/wikiChannels.mutations';
import { useWikiFavoriteToggleMutation } from '../../queries/wikiFavorites.mutations';
import { wikiChannelHref, wikiFolderHref } from '../../utils/wikiNavTree';
import MoveTargetPicker, { type MoveTarget, type MoveTargetChannel } from './MoveTargetPicker';

/** 액션 버튼이 붙은 토스트는 누를 시간이 필요해 기본 표시 시간보다 길게 둔다 */
const ACTION_TOAST_DURATION = 6000;

/** 위키 SNB에 실 데이터를 물리는 자리. shared 층은 features를 import할 수 없어 여기서 잇는다. */
export default function WikiSideNavContainer() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { treeNodes, favorites, channelAdmins, onNodeToggle } = useWikiSideNav();
  const { data: me } = useQuery(authQueries.me());
  const favoriteToggle = useWikiFavoriteToggleMutation();
  const renameChannel = useRenameWikiChannelMutation();
  const renameFolder = useRenameWikiFolderMutation();
  const createFolder = useCreateWikiFolderMutation();
  const moveArtifact = useMoveWikiArtifactMutation();

  // 옮기기 대상 패널. 케밥이 섰던 앵커에 이어 뜨고, 본문이 features 데이터라 팝오버째 여기서 소유한다
  const [movePicker, setMovePicker] = useState<{ node: WikiTreeNode; anchor: HTMLElement } | null>(null);

  // 이동 API가 같은 채널 안만 받아 대상을 그 문서의 채널 하나로 좁히고, 현재 자리는 트리의 부모로 찾는다
  const moveTarget = useMemo<{ channel: MoveTargetChannel; currentFolderId: string | null } | undefined>(() => {
    const channel = movePicker ? treeNodes.find((node) => node.id === movePicker.node.channelId) : undefined;
    if (!movePicker || !channel) return undefined;
    const folders = (channel.children ?? []).filter((child) => child.kind === 'folder');
    const parentFolder = folders.find((folder) => (folder.children ?? []).some((doc) => doc.id === movePicker.node.id));
    // 즐겨찾기에서 온 문서는 채널을 펼치기 전이라 트리에 없을 수 있다 — 즐겨찾기 데이터의 폴더로 보완한다
    const favoriteFolderId = favorites.find((item) => item.id === movePicker.node.id)?.folderId ?? null;
    return {
      channel: {
        id: channel.id,
        label: channel.label,
        folders: folders.map((folder) => ({ id: folder.id, label: folder.label })),
      },
      currentFolderId: parentFolder?.id ?? favoriteFolderId,
    };
  }, [treeNodes, favorites, movePicker]);

  // 노드가 들고 있는 경로에 현재 오리진을 붙인다 — 공유 링크 규격이 따로 없다
  const copyNodeLink = async (nodeId: string) => {
    // 즐겨찾기 행의 문서는 채널을 펼치기 전이라 트리에 없을 수 있다
    const href = findTreeNode(treeNodes, nodeId)?.href ?? favorites.find((item) => item.id === nodeId)?.href;
    if (href === undefined) return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${href}`);
      toast('링크가 복사되었습니다.');
    } catch {
      toast('복사에 실패했습니다.');
    }
  };

  // 즐겨찾기 항목은 문서 행에만 뜬다 — 그 노드 id가 곧 artifact_id다
  const handleMenuAction = (nodeId: string | undefined, actionId: SnbMenuActionId) => {
    if (nodeId === undefined) return;
    if (actionId === 'favorite' || actionId === 'unfavorite') {
      favoriteToggle.mutate({ artifactId: nodeId, favorite: actionId === 'favorite' });
      return;
    }
    if (actionId === 'copy-link') void copyNodeLink(nodeId);
  };

  // 문서는 이름 변경 API가 없어 채널·폴더만 여기로 온다
  const handleRenameSubmit = (node: WikiTreeNode, name: string) => {
    if (node.kind === 'channel') renameChannel.mutate({ channelId: node.id, name });
    else if (node.kind === 'folder') renameFolder.mutate({ channelId: node.channelId, folderId: node.id, name });
  };

  const handleFolderCreateSubmit = (channelNode: WikiTreeNode, name: string) => {
    createFolder.mutate({ channelId: channelNode.channelId, name });
  };

  const handleMoveSelect = (node: WikiTreeNode, target: MoveTarget) => {
    const href = target.folderId === null ? wikiChannelHref(target.channelId) : wikiFolderHref(target.folderId);
    moveArtifact.mutate(
      { artifactId: node.id, folderId: target.folderId },
      {
        onSuccess: () => {
          toast(`${node.label}의 옮긴 위치는 ${target.label} 입니다.`, {
            duration: ACTION_TOAST_DURATION,
            action: { label: '이동', onClick: () => router.push(href) },
            classNames: { actionButton: buttonVariants({ variant: 'box-outline-gray', size: 'sm' }) },
          });
        },
      },
    );
  };

  // 패널에서 새 폴더를 만들면 목록을 다시 읽어 그 폴더로 곧장 옮긴다(이름 중복은 서버가 409로 막는다)
  const handleCreateFolderAndMove = async (name: string) => {
    if (!movePicker || !moveTarget) return;
    const node = movePicker.node;
    const channelId = moveTarget.channel.id;
    try {
      await createFolder.mutateAsync({ channelId, name });
    } catch {
      return; // 실패 토스트는 뮤테이션 훅이 띄운다
    }
    const channels = await queryClient.fetchQuery(wikiQueries.channels());
    const folder = channels.channels.find((item) => item.id === channelId)?.folders.find((item) => item.name === name);
    if (!folder) return;
    setMovePicker(null);
    handleMoveSelect(node, { channelId, folderId: folder.id, label: folder.name });
  };

  return (
    <>
      <WikiSideNav
        canCreateWiki={me?.role === 'admin'}
        treeNodes={treeNodes}
        favorites={favorites}
        channelAdmins={channelAdmins}
        onNodeToggle={onNodeToggle}
        onMenuAction={handleMenuAction}
        onRenameSubmit={handleRenameSubmit}
        onFolderCreateSubmit={handleFolderCreateSubmit}
        onMoveRequest={(node, anchor) => setMovePicker({ node, anchor })}
        moveOpenNodeId={movePicker?.node.id}
      />

      {/* 케밥과 같은 앵커에 virtualRef로 붙는다 — 껍데기 규격은 SNB 팝오버 공통이다 */}
      {movePicker && (
        <Popover open onOpenChange={(open) => !open && setMovePicker(null)}>
          <PopoverAnchor virtualRef={{ current: movePicker.anchor }} />
          <PopoverContent align="start" side="right" className={SNB_POPOVER_SHELL_CLASS}>
            <MoveTargetPicker
              channel={moveTarget?.channel}
              currentFolderId={moveTarget?.currentFolderId}
              onSelect={(target) => {
                setMovePicker(null);
                handleMoveSelect(movePicker.node, target);
              }}
              onCreateFolder={
                moveTarget && channelAdmins[moveTarget.channel.id] === true
                  ? (name) => void handleCreateFolderAndMove(name)
                  : undefined
              }
            />
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}
