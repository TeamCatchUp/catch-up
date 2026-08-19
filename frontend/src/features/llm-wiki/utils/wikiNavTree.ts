/** 위키 SNB 트리·즐겨찾기 조립. 순수 함수이고 요청·캐시를 알지 못한다. */

import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import type { WikiSideNavFavorite, WikiTreeNode } from '@/shared/components/layout/sideNavBar/WikiSideNav';

import type { WikiArtifactListItemDto, WikiChannelListItemDto, WikiFavoriteItemDto } from '../api/wikiDto';

export const wikiChannelHref = (channelId: string) => `/llm-wiki/channel/${channelId}`;
export const wikiFolderHref = (folderId: string) => `/llm-wiki/folder/${folderId}`;
export const wikiDocumentHref = (artifactId: string) => `/llm-wiki/${artifactId}`;

/** 최종 편집자·시각(케밥 하단 metaLines)에 대응하는 필드가 목록 응답에 없어 채우지 않는다. */
function documentNode(dto: WikiArtifactListItemDto, channelId: string): WikiTreeNode {
  return {
    id: dto.artifact_id,
    kind: 'document',
    channelId,
    href: wikiDocumentHref(dto.artifact_id),
    label: dto.title,
    Icon: IconFile,
    favorite: dto.is_favorite,
  };
}

/**
 * 채널 목록 + 받아온 문서로 트리를 만든다. 채널 응답이 폴더를 동봉해 2단계는 한 번에 서고,
 * 문서는 그 채널을 펼쳐 받아왔을 때만 붙는다.
 */
export function buildWikiNavTree(
  channels: readonly WikiChannelListItemDto[],
  documentsByChannel: ReadonlyMap<string, readonly WikiArtifactListItemDto[]>,
): WikiTreeNode[] {
  return channels.map((channel) => {
    const documents = documentsByChannel.get(channel.id) ?? [];

    const folders: WikiTreeNode[] = channel.folders.map((folder) => {
      const children = documents.filter((item) => item.folder_id === folder.id).map((item) => documentNode(item, channel.id));
      return {
        id: folder.id,
        kind: 'folder',
        channelId: channel.id,
        href: wikiFolderHref(folder.id),
        label: folder.name,
        Icon: IconFolder,
        canAddChild: true,
        children: children.length > 0 ? children : undefined,
      };
    });

    // 채널 루트 문서만 채널 아래에 둔다 — 폴더 소속 문서는 그 폴더 아래에 이미 붙었다
    const rootDocuments = documents.filter((item) => item.folder_id === null).map((item) => documentNode(item, channel.id));
    const children = [...folders, ...rootDocuments];

    return {
      id: channel.id,
      kind: 'channel',
      channelId: channel.id,
      href: wikiChannelHref(channel.id),
      label: channel.name,
      Icon: IconWikiChannel,
      canAddChild: true,
      children: children.length > 0 ? children : undefined,
    };
  });
}

/** 채널 id → 관리자 여부. A8 게이트(하위 추가·이름 바꾸기)가 이 맵만 본다 */
export function buildWikiChannelAdmins(channels: readonly WikiChannelListItemDto[]): Record<string, boolean> {
  return Object.fromEntries(channels.map((channel) => [channel.id, channel.is_admin]));
}

export function buildWikiFavorites(items: readonly WikiFavoriteItemDto[]): WikiSideNavFavorite[] {
  return items.map((item) => ({
    id: item.artifact_id,
    label: item.title,
    href: wikiDocumentHref(item.artifact_id),
  }));
}
