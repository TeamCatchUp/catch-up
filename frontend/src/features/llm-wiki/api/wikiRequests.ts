/** /api/v1/wiki/* 요청 함수. 응답은 서버 DTO 그대로 돌려주고 변환은 매퍼가 맡는다. */

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  WikiArtifactDocumentDto,
  WikiArtifactListDto,
  WikiArtifactListParams,
  WikiChannelListDto,
  WikiDefinitionPresetsDto,
  WikiFavoriteListDto,
  WikiWorkspaceMemberListDto,
} from './wikiDto';

export async function fetchWikiChannels(signal?: AbortSignal): Promise<WikiChannelListDto> {
  const res = await api.get<WikiChannelListDto>(API.wiki.channels, { signal });
  return res.data;
}

export async function fetchWikiDefinitionPresets(signal?: AbortSignal): Promise<WikiDefinitionPresetsDto> {
  const res = await api.get<WikiDefinitionPresetsDto>(API.wiki.definitionPresets, { signal });
  return res.data;
}

/** 활성 구성원만 온다 — 비활성·삭제된 사용자는 담당자 후보에서 빠진다. */
export async function fetchWikiMembers(signal?: AbortSignal): Promise<WikiWorkspaceMemberListDto> {
  const res = await api.get<WikiWorkspaceMemberListDto>(API.wiki.members, { signal });
  return res.data;
}

/**
 * owner_user_id는 반복 파라미터로 나가야 서버가 읽는다 —
 * axios 기본 직렬화는 `owner_user_id[]=`라 FastAPI가 값을 못 찾는다.
 */
export async function fetchWikiArtifacts(
  params: WikiArtifactListParams,
  signal?: AbortSignal,
): Promise<WikiArtifactListDto> {
  const res = await api.get<WikiArtifactListDto>(API.wiki.artifacts, {
    params,
    paramsSerializer: { indexes: null },
    signal,
  });
  return res.data;
}

/** 발행된 판이 없는 문서는 404다 — 계류 변경안은 이 경로로 나오지 않는다. */
export async function fetchWikiArtifactDocument(
  artifactId: string,
  signal?: AbortSignal,
): Promise<WikiArtifactDocumentDto> {
  const res = await api.get<WikiArtifactDocumentDto>(API.wiki.artifact(artifactId), { signal });
  return res.data;
}

export async function fetchWikiFavorites(signal?: AbortSignal): Promise<WikiFavoriteListDto> {
  const res = await api.get<WikiFavoriteListDto>(API.wiki.favorites, { signal });
  return res.data;
}

/** 즐겨찾기 등록(멱등). 문서(artifact) 단위라 채널·폴더에는 보낼 경로가 없다. */
export async function addWikiFavorite(artifactId: string): Promise<void> {
  await api.put(API.wiki.favorite(artifactId));
}

/** 즐겨찾기 해제(멱등). 등록과 같은 자리를 뒤집는다. */
export async function removeWikiFavorite(artifactId: string): Promise<void> {
  await api.delete(API.wiki.favorite(artifactId));
}

/** 문서 폴더 이동(검수 자격자). folder_id가 null이면 채널 바로 아래로 옮긴다. */
export async function moveWikiArtifact(artifactId: string, folderId: string | null): Promise<void> {
  await api.patch(API.wiki.artifact(artifactId), { folder_id: folderId });
}

/** 채널 이름 변경(채널 관리자). 응답 본문은 쓰지 않는다. */
export async function renameWikiChannel(channelId: string, name: string): Promise<void> {
  await api.patch(API.wiki.channel(channelId), { name });
}

/** 폴더 생성(채널 관리자). 폴더는 채널 바로 아래에만 생긴다. */
export async function createWikiFolder(channelId: string, name: string): Promise<void> {
  await api.post(API.wiki.folders(channelId), { name });
}

/** 폴더 이름 변경(채널 관리자). 폴더 경로가 채널 아래라 소속 채널 id가 함께 필요하다. */
export async function renameWikiFolder(channelId: string, folderId: string, name: string): Promise<void> {
  await api.patch(API.wiki.folder(channelId, folderId), { name });
}
