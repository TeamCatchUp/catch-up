'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
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
  const { treeNodes, favorites, channelAdmins, onNodeToggle } = useWikiSideNav();
  const { data: me } = useQuery(authQueries.me());
  const favoriteToggle = useWikiFavoriteToggleMutation();
  const renameChannel = useRenameWikiChannelMutation();
  const renameFolder = useRenameWikiFolderMutation();
  const createFolder = useCreateWikiFolderMutation();
  const moveArtifact = useMoveWikiArtifactMutation();

  // 옮기기 대상 패널. 케밥이 섰던 앵커에 이어 뜨고, 본문이 features 데이터라 팝오버째 여기서 소유한다
  const [movePicker, setMovePicker] = useState<{ node: WikiTreeNode; anchor: HTMLElement } | null>(null);

  // 옮길 곳 목록은 트리가 이미 들고 있다 — 채널 응답이 폴더를 동봉해 추가 왕복이 없다
  const moveTargetChannels = useMemo<readonly MoveTargetChannel[]>(
    () =>
      treeNodes.map((channel) => ({
        id: channel.id,
        label: channel.label,
        folders: (channel.children ?? [])
          .filter((child) => child.kind === 'folder')
          .map((folder) => ({ id: folder.id, label: folder.label })),
      })),
    [treeNodes],
  );

  // 노드가 들고 있는 경로에 현재 오리진을 붙인다 — 공유 링크 규격이 따로 없다
  const copyNodeLink = async (nodeId: string) => {
    const node = findTreeNode(treeNodes, nodeId);
    if (!node) return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${node.href}`);
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
              channels={moveTargetChannels}
              onSelect={(target) => {
                setMovePicker(null);
                handleMoveSelect(movePicker.node, target);
              }}
            />
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}
