/** GET /api/v1/wiki/* 요청 함수. 응답은 서버 DTO 그대로 돌려주고 변환은 매퍼가 맡는다. */

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

export async function fetchWikiArtifacts(
  params: WikiArtifactListParams,
  signal?: AbortSignal,
): Promise<WikiArtifactListDto> {
  const res = await api.get<WikiArtifactListDto>(API.wiki.artifacts, { params, signal });
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
