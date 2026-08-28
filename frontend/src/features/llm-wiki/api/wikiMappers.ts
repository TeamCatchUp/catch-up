/** wiki DTO → 도메인 타입 변환. 전부 순수 함수이고 요청·캐시를 알지 못한다. */

import { formatRelativeTime } from '@/shared/utils/formatDate';

import type {
  DocumentBreadcrumb,
  DocumentOwner,
  DocumentRowData,
  DocumentStatus,
  WikiChannelListItem,
  WikiFolder,
} from '../types/llmWikiModel';
import type {
  WikiArtifactListItemDto,
  WikiArtifactStatusDto,
  WikiChannelListDto,
  WikiChannelListItemDto,
  WikiFolderDto,
  WikiOwnerDto,
  WikiWorkspaceMemberListDto,
} from './wikiDto';

export function mapWikiOwner(dto: WikiOwnerDto): DocumentOwner {
  return {
    userId: dto.user_id,
    displayName: dto.display_name,
    profileImageUrl: dto.profile_image_url,
  };
}

export function mapWikiOwners(dtos: readonly WikiOwnerDto[]): DocumentOwner[] {
  return dtos.map(mapWikiOwner);
}

/** 담당자 피커의 후보 명단. 항목이 owners[]와 같은 모양이라 같은 변환을 쓴다. */
export function mapWikiMembers(dto: WikiWorkspaceMemberListDto): DocumentOwner[] {
  return mapWikiOwners(dto.items);
}

/** 담당자와 같은 모양의 선택 필드용 변환. null은 "그 사람이 없다"라 그대로 통과시킨다. */
export function mapWikiOptionalOwner(dto: WikiOwnerDto | null | undefined): DocumentOwner | null {
  return dto ? mapWikiOwner(dto) : null;
}

export function mapWikiFolder(dto: WikiFolderDto): WikiFolder {
  return {
    id: dto.id,
    name: dto.name,
    channelId: dto.channel_id,
    createdAt: dto.created_at,
    createdBy: mapWikiOptionalOwner(dto.created_by),
    lastActivityAt: dto.last_activity_at,
  };
}

export function mapWikiChannelListItem(dto: WikiChannelListItemDto): WikiChannelListItem {
  return {
    id: dto.id,
    name: dto.name,
    workspaceId: dto.workspace_id,
    isAdmin: dto.is_admin,
    documentCount: dto.document_count,
    folders: dto.folders.map(mapWikiFolder),
  };
}

export function mapWikiChannelList(dto: WikiChannelListDto): WikiChannelListItem[] {
  return dto.channels.map(mapWikiChannelListItem);
}

/**
 * 서버 파생 상태 → 문서 상태. published만 reviewed로 옮기고 나머지는 그대로 통과시킨다.
 * no_revision은 대응 배지가 없어 렌더되지 않는 것이 정상이다.
 */
export function mapDocumentStatus(status: WikiArtifactStatusDto): DocumentStatus {
  return status === 'published' ? 'reviewed' : status;
}

/** 문서 응답이 주는 channel_id·folder_id를 이름으로 바꾸기 위한 색인. */
export interface WikiLocationIndex {
  channelNames: ReadonlyMap<string, string>;
  folderNames: ReadonlyMap<string, string>;
}

/** 채널 목록 응답 하나로 채널·폴더 이름 색인을 만든다. 폴더 id는 전역 UUID라 한 장으로 충분하다. */
export function createWikiLocationIndex(channels: readonly WikiChannelListItemDto[]): WikiLocationIndex {
  const channelNames = new Map<string, string>();
  const folderNames = new Map<string, string>();

  for (const channel of channels) {
    channelNames.set(channel.id, channel.name);
    for (const folder of channel.folders) folderNames.set(folder.id, folder.name);
  }

  return { channelNames, folderNames };
}

/**
 * 문서의 위치 id를 채널 > 폴더 경로로 푼다. 색인에 없는 id는 마디를 만들지 않는다 —
 * 이름 대신 UUID가 화면에 나가는 것보다 마디가 비는 편이 낫다.
 */
export function resolveDocumentBreadcrumbs(
  index: WikiLocationIndex,
  channelId: string | null,
  folderId: string | null,
): DocumentBreadcrumb[] {
  const breadcrumbs: DocumentBreadcrumb[] = [];

  if (channelId !== null) {
    const channelName = index.channelNames.get(channelId);
    if (channelName !== undefined) breadcrumbs.push({ kind: 'channel', label: channelName, id: channelId });
  }

  if (folderId !== null) {
    const folderName = index.folderNames.get(folderId);
    if (folderName !== undefined) breadcrumbs.push({ kind: 'folder', label: folderName, id: folderId });
  }

  return breadcrumbs;
}

/** 문서 목록 한 줄 → 표의 행. breadcrumbs는 채널 목록과의 join 결과라 밖에서 받는다. */
export function mapWikiArtifactRow(
  dto: WikiArtifactListItemDto,
  breadcrumbs: readonly DocumentBreadcrumb[] = [],
): DocumentRowData {
  return {
    id: dto.artifact_id,
    title: dto.title,
    breadcrumbs,
    status: mapDocumentStatus(dto.status),
    owners: mapWikiOwners(dto.owners),
    createdAt: dto.created_at,
    lastActivityAt: dto.last_activity_at,
    lastActivityLabel: formatRelativeTime(dto.last_activity_at),
    lastEditedBy: mapWikiOptionalOwner(dto.last_edited_by),
    lastEditedAt: dto.last_edited_at,
  };
}

/** 색인을 주면 경로까지 채워 한 쪽을 옮긴다. 색인이 없으면 경로는 빈 배열이다. */
export function mapWikiArtifactRows(
  items: readonly WikiArtifactListItemDto[],
  index?: WikiLocationIndex,
): DocumentRowData[] {
  return items.map((item) =>
    mapWikiArtifactRow(item, index ? resolveDocumentBreadcrumbs(index, item.channel_id, item.folder_id) : []),
  );
}
