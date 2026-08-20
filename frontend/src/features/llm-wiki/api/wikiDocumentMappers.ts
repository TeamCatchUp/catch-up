/** 발행판 상세 DTO → 문서 열람 화면 계약. 순수 함수라 요청·캐시를 알지 못한다. */

import { formatRelativeTime } from '@/shared/utils/formatDate';

import type { DocumentOwner } from '../types/llmWikiModel';
import type { WikiArtifactDocumentDto, WikiBlockSourceDto, WikiDocumentBlockDto } from './wikiDto';
import { mapWikiOwners } from './wikiMappers';

/**
 * [BE] 블록 문장의 근거 인용. citationVerified는 검증/대조 실패/근거 없음 3값이다.
 * 표시 시안이 없어 화면에 나가지 않고 계약만 보존한다.
 */
export interface WikiDocumentSource {
  claimId: string;
  statement: string;
  observedAt: string;
  citationVerified: boolean | null;
}

/**
 * [BE] 발행판 블록 하나. 검토 큐의 WikiBlock과 달리 판정·다툼·지문 필드가 없다 —
 * 발행된 판에는 판정할 것이 남아 있지 않기 때문이다.
 */
export interface WikiDocumentBlock {
  /** [BE] 목록에서의 자리. 블록 고유 id가 없어 이 값이 식별자다 */
  blockIndex: number;
  /** [BE] 블록 종류. 목록이 흔들려 닫지 않는다 */
  kind: string;
  heading: string;
  /** [BE] 사람용 산문. 이쪽이 표시 정본이고 body는 값 표기다 */
  narrative: string | null;
  /** 플레인 문자열 — 인라인 서식 없음 */
  body: string;
  claimIds: readonly string[];
  relationIds: readonly string[];
  sources: readonly WikiDocumentSource[];
}

/** 지금 발행된 판 하나. 발행판이 없는 문서는 이 계약에 도달하지 못한다(404) */
export interface WikiDocumentData {
  artifactId: string;
  channelId: string | null;
  folderId: string | null;
  kind: string;
  title: string;
  owners: readonly DocumentOwner[];
  isFavorite: boolean;
  revisionId: string;
  /** [BE] 이 판이 발행된 시각(ISO). 판은 덮어쓰지 않고 쌓인다 */
  publishedAt: string;
  /** 발행 시각 표시 문자열 (예: "3시간 전") */
  publishedLabel: string;
  blocks: readonly WikiDocumentBlock[];
}

/** 화면에 실리는 본문. 산문이 정본이고 없으면 값 표기로 폴백한다 — 검토 큐 diff와 같은 규칙이다 */
export function resolveDocumentBlockText(block: WikiDocumentBlock): string {
  return block.narrative ?? block.body;
}

export function mapWikiDocumentSource(dto: WikiBlockSourceDto): WikiDocumentSource {
  return {
    claimId: dto.claim_id,
    statement: dto.statement,
    observedAt: dto.observed_at,
    citationVerified: dto.citation_verified,
  };
}

export function mapWikiDocumentBlock(dto: WikiDocumentBlockDto): WikiDocumentBlock {
  return {
    blockIndex: dto.block_index,
    kind: dto.block_kind,
    heading: dto.heading,
    narrative: dto.narrative,
    body: dto.body,
    claimIds: dto.claim_ids,
    relationIds: dto.relation_ids,
    sources: dto.sources.map(mapWikiDocumentSource),
  };
}

export function mapWikiArtifactDocument(dto: WikiArtifactDocumentDto): WikiDocumentData {
  return {
    artifactId: dto.artifact_id,
    channelId: dto.channel_id,
    folderId: dto.folder_id,
    kind: dto.kind,
    title: dto.title,
    owners: mapWikiOwners(dto.owners),
    isFavorite: dto.is_favorite,
    revisionId: dto.revision_id,
    publishedAt: dto.published_at,
    publishedLabel: formatRelativeTime(dto.published_at),
    blocks: dto.blocks.map(mapWikiDocumentBlock),
  };
}
