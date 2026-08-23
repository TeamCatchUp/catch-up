/**
 * GET/POST /api/v1/wiki/* 의 서버 DTO. 필드는 응답 그대로 snake_case다.
 * 원천은 backend/catchup/server/wiki/{api,schemas}.py — camelCase 변환은 매퍼 몫이다.
 */

/** 담당자 한 명. profile_image_url은 사진이 없을 수 있어 null을 허용한다 */
export interface WikiOwnerDto {
  user_id: number;
  display_name: string;
  profile_image_url: string | null;
}

export interface WikiChannelDto {
  id: string;
  name: string;
  workspace_id: number;
}

/** 폴더. 채널 바로 아래 한 겹뿐이라 상위 폴더 필드가 없다 */
export interface WikiFolderDto {
  id: string;
  name: string;
  channel_id: string;
  created_at: string;
  /** 만든 사람. 컬럼이 생기기 전 폴더와 사용자 행이 사라진 폴더는 null이다 */
  created_by: WikiOwnerDto | null;
  /** 폴더 안 문서가 마지막으로 움직인 시각. 문서가 없으면 null이다 */
  last_activity_at: string | null;
}

/** 채널 안 정의 하나. folder_id가 null이면 채널 루트에 놓인다 */
export interface WikiDefinitionSummaryDto {
  definition_id: string;
  kind: string;
  folder_id: string | null;
  purpose_presets: string[];
}

export interface WikiChannelListItemDto {
  id: string;
  name: string;
  workspace_id: number;
  is_admin: boolean;
  document_count: number;
  folders: WikiFolderDto[];
  purpose_presets: string[];
  definitions: WikiDefinitionSummaryDto[];
}

export interface WikiChannelListDto {
  channels: WikiChannelListItemDto[];
}

/** 문서 목록 응답의 파생 상태. 컬럼이 아니라 계류 제안 수와 최신 판에서 계산된다 */
export type WikiArtifactStatusDto = 'pending_review' | 'published' | 'no_revision';

export interface WikiLatestRevisionDto {
  revision_id: string;
  revision_number: number;
  published_at: string;
}

export interface WikiArtifactListItemDto {
  artifact_id: string;
  kind: string;
  title: string;
  channel_id: string | null;
  folder_id: string | null;
  created_at: string;
  /** 마지막 발행 시각과 마지막 변경안 도착 시각 중 늦은 쪽, 둘 다 없으면 생성 시각. 항상 값이 있다 */
  last_activity_at: string;
  status: WikiArtifactStatusDto;
  pending_proposal_count: number;
  latest_revision: WikiLatestRevisionDto | null;
  owners: WikiOwnerDto[];
  is_favorite: boolean;
  /** 가장 최근 발행판의 승인자. 승인자가 사용자로 이어지지 않으면 null이다 */
  last_edited_by: WikiOwnerDto | null;
  /** 그 승인 시각. 발행판이 없으면 사람과 함께 null이다 */
  last_edited_at: string | null;
}

/** total은 limit·offset을 걸기 전의 수다 — 쪽 수 계산의 유일한 재료다 */
export interface WikiArtifactListDto {
  items: WikiArtifactListItemDto[];
  total: number;
  limit: number;
  offset: number;
}

export interface WikiBlockSourceDto {
  claim_id: string;
  statement: string;
  observed_at: string;
  citation_verified: boolean | null;
}

export interface WikiDocumentBlockDto {
  block_index: number;
  block_kind: string;
  heading: string;
  narrative: string | null;
  body: string;
  claim_ids: string[];
  relation_ids: string[];
  sources: WikiBlockSourceDto[];
}

/** 읽기 레이아웃 표의 한 행. label이 양식이 정한 칸 이름이고 value가 그 칸 값이다 */
export interface WikiLayoutTableRowDto {
  label: string;
  value: string;
}

/**
 * 읽기 레이아웃 항목. item_kind는 block·table·placeholder지만 늘 수 있어 닫지 않는다.
 * block_index는 blocks[] 자리 그대로이고 표시 순서에 맞춰 재번호하지 않는다.
 */
export interface WikiLayoutItemDto {
  item_kind: string;
  heading: string;
  block_index?: number | null;
  /** table 항목이 합친 블록 자리들. rows[i]가 block_indexes[i]에서 나온다 */
  block_indexes?: number[];
  rows?: WikiLayoutTableRowDto[];
  /** placeholder 항목의 문구. 가리킬 블록이 없다 */
  text?: string | null;
}

/** 지금 발행된 판 하나. 발행판이 없는 문서는 이 경로가 404다 */
export interface WikiArtifactDocumentDto {
  artifact_id: string;
  channel_id: string | null;
  definition_id: string | null;
  kind: string;
  title: string;
  folder_id: string | null;
  owners: WikiOwnerDto[];
  is_favorite: boolean;
  revision_id: string;
  published_at: string;
  /** 지금 발행된 판의 승인자. 승인자가 사용자로 이어지지 않으면 null이다 */
  last_edited_by: WikiOwnerDto | null;
  /** 그 승인 시각. 사람이 null이어도 시각은 채워질 수 있다 */
  last_edited_at: string | null;
  blocks: WikiDocumentBlockDto[];
  /** 표시 순서·이름만 정한다. 내용과 근거의 원천은 blocks다 — 구서버 응답에는 없다 */
  layout?: WikiLayoutItemDto[];
}

export interface WikiFavoriteItemDto {
  artifact_id: string;
  title: string;
  kind: string;
  channel_id: string | null;
  folder_id: string | null;
  favorited_at: string;
}

export interface WikiFavoriteListDto {
  items: WikiFavoriteItemDto[];
}

export interface WikiFavoriteDto {
  artifact_id: string;
  is_favorite: boolean;
}

export interface WikiArtifactLocationDto {
  artifact_id: string;
  channel_id: string | null;
  folder_id: string | null;
}

/** 지정 후의 담당자 명단 전체. 멱등이라 응답 코드만으로는 지금 명단을 알 수 없다 */
export interface WikiArtifactOwnerDto {
  artifact_id: string;
  owners: WikiOwnerDto[];
}

export interface WikiChannelAdminDto {
  channel_id: string;
  user_ids: number[];
}

export interface WikiPresetKindDto {
  kind: string;
  label: string;
  description: string;
  example_text: string;
}

export interface WikiPresetPurposeDto {
  id: string;
  label: string;
  recommended_kind: string;
}

export interface WikiPresetDomainDto {
  id: string;
  label: string;
  purposes: WikiPresetPurposeDto[];
  kinds: WikiPresetKindDto[];
}

export interface WikiPresetStyleDto {
  id: string;
  label: string;
}

export interface WikiDefinitionPresetsDto {
  domains: WikiPresetDomainDto[];
  styles: WikiPresetStyleDto[];
}

/** vocabulary_version이 null이면 더할 어휘가 없어 발행을 건너뛴 것이다 */
export interface WikiChannelOnboardingDto {
  channel: WikiChannelDto;
  domain_preset: string;
  purpose_presets: string[];
  style_preset: string;
  vocabulary_version: string | null;
  definitions: WikiDefinitionSummaryDto[];
}

/** 정렬 키. 기본은 last_activity다 */
export type WikiArtifactSortKey = 'last_activity' | 'created_at';
export type WikiArtifactSortOrder = 'asc' | 'desc';

/** status는 프론트 도메인 상태가 아니라 서버 파생 상태 3값이다. */
interface WikiArtifactListBaseParams {
  channel_id?: string;
  folder_id?: string;
  kind?: string;
  status?: WikiArtifactStatusDto;
  /** 제목 부분 일치 */
  q?: string;
  /** ISO 8601 문자열. 서버가 datetime으로 파싱한다 */
  created_after?: string;
  created_before?: string;
  /** 기본 last_activity */
  sort?: WikiArtifactSortKey;
  /** 기본 desc */
  order?: WikiArtifactSortOrder;
  /** 1~200. 기본 50 */
  limit?: number;
  offset?: number;
}

/**
 * 담당자 조건은 둘 중 하나만 실린다 — 함께 주면 서버가 422(CONFLICTING_OWNER_FILTERS)다.
 * owner_user_id는 여러 명을 받고 그중 한 명이라도 담당인 문서를 모두 돌려준다.
 */
type WikiArtifactOwnerFilter =
  | { owner_user_id?: number[]; unassigned?: never }
  | { owner_user_id?: never; unassigned?: boolean };

export type WikiArtifactListParams = WikiArtifactListBaseParams & WikiArtifactOwnerFilter;

/** 담당자 피커의 후보 명단. 항목 모양이 owners[]와 같아 화면이 한 타입으로 다룬다 */
export interface WikiWorkspaceMemberListDto {
  items: WikiOwnerDto[];
}

export interface WikiChannelCreateRequest {
  name: string;
}

export interface WikiChannelRenameRequest {
  name: string;
}

/** name은 20자 제한이고 purpose_presets·kinds는 최소 1개가 필요하다 */
export interface WikiChannelOnboardingRequest {
  name: string;
  domain_preset: string;
  purpose_presets: string[];
  kinds: string[];
  style_preset: string;
}

export interface WikiFolderCreateRequest {
  name: string;
}

export interface WikiFolderRenameRequest {
  name: string;
}

/** folder_id 키는 필수이고 값만 null을 받는다 — null은 채널 루트로 올리라는 뜻이다 */
export interface WikiArtifactMoveRequest {
  folder_id: string | null;
}
