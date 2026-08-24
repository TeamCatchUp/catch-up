/** knowledge-review DTO → 도메인 타입 변환. 전부 순수 함수다. */

import { formatRelativeTime } from '@/shared/utils/formatDate';

import type { BlockSource, BlockVariant, BlockVerdict, WikiBlock } from '../types/llmWikiDiff';
import type { ChangeProposalStatus, ReviewQueueItemData } from '../types/llmWikiModel';
import type {
  ReviewBaseBlockDto,
  ReviewBlockDto,
  ReviewBlockSourceDto,
  ReviewBlockVerdictDto,
  ReviewQueueItemDto,
  ReviewVariantDto,
} from './knowledgeReviewDto';
import { mapWikiOwners } from './wikiMappers';

export function mapBlockSource(dto: ReviewBlockSourceDto): BlockSource {
  return {
    claimId: dto.claim_id,
    statement: dto.statement,
    observedAt: dto.observed_at,
    citationVerified: dto.citation_verified,
  };
}

export function mapBlockVariant(dto: ReviewVariantDto): BlockVariant {
  return {
    claimId: dto.claim_id,
    body: dto.body,
    sources: dto.sources.map(mapBlockSource),
  };
}

export function mapBlockVerdict(dto: ReviewBlockVerdictDto): BlockVerdict {
  return {
    proposalId: dto.proposal_id,
    blockIndex: dto.block_index,
    blockContentHash: dto.block_content_hash,
    verdict: dto.verdict,
    rejectionReason: dto.rejection_reason,
    chosenWinnerClaimId: dto.chosen_winner_claim_id,
    reviewer: dto.reviewer,
    reviewedAt: dto.reviewed_at,
  };
}

/** 변경안 블록. markdown은 도메인 계약에 자리가 없어 옮기지 않는다 — 정본은 heading·body·narrative다. */
export function mapReviewBlock(dto: ReviewBlockDto): WikiBlock {
  return {
    blockIndex: dto.block_index,
    kind: dto.block_kind,
    heading: dto.heading,
    body: dto.body,
    narrative: dto.narrative,
    claimIds: dto.claim_ids,
    proposalIds: dto.proposal_ids,
    ontologyVersion: dto.ontology_version,
    blockContentHash: dto.block_content_hash,
    sources: dto.sources.map(mapBlockSource),
    variants: dto.variants === null ? null : dto.variants.map(mapBlockVariant),
    verdict: dto.verdict === null ? null : mapBlockVerdict(dto.verdict),
    reason: dto.change_reason,
  };
}

/**
 * 발행판 블록. 서버가 지문·판정을 싣지 않으므로 빈 지문과 null 판정으로 채운다 —
 * 발행판 블록에는 결정을 보낼 경로가 없다는 계약을 그대로 옮긴 값이다.
 */
export function mapReviewBaseBlock(dto: ReviewBaseBlockDto): WikiBlock {
  return {
    blockIndex: dto.block_index,
    kind: dto.block_kind,
    heading: dto.heading,
    body: dto.body,
    narrative: dto.narrative,
    claimIds: dto.claim_ids,
    proposalIds: [],
    ontologyVersion: null,
    blockContentHash: '',
    sources: dto.sources.map(mapBlockSource),
    variants: null,
    verdict: null,
  };
}

const CHANGE_PROPOSAL_STATUSES: readonly ChangeProposalStatus[] = ['pending', 'approved', 'rejected', 'abandoned'];

/** 제안 판정은 DB CHECK로 닫힌 집합이다. 그 밖의 값은 큐가 계류만 싣는다는 계약을 따라 pending으로 읽는다. */
export function mapChangeProposalStatus(status: string): ChangeProposalStatus {
  return CHANGE_PROPOSAL_STATUSES.find((known) => known === status) ?? 'pending';
}

/**
 * 큐 목록 한 줄. baseRevisionId는 목록 응답에 없어 뺀다 —
 * stale 판정 키는 상세 응답(base_revision_id)에서만 온다.
 */
export type ReviewQueueRowData = Omit<ReviewQueueItemData, 'baseRevisionId'>;

/**
 * 큐 한 줄 → 목록 행. type에는 origin(compiled·manual)을 그대로 싣는다 —
 * 큐 응답의 유형 축은 이것뿐이고 명세의 6유형과 겹치지 않는다.
 */
export function mapReviewQueueItem(dto: ReviewQueueItemDto): ReviewQueueRowData {
  return {
    id: dto.proposal_id,
    type: dto.origin,
    title: dto.artifact.title ?? dto.summary,
    owners: mapWikiOwners(dto.owners),
    waitingLabel: formatRelativeTime(dto.created_at),
    status: mapChangeProposalStatus(dto.status),
    rejectionReason: null,
    hasConflictIcon: dto.contains_conflict,
    canReview: dto.can_review,
  };
}
