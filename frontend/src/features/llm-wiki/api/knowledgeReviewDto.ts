/**
 * GET/PUT/POST /api/v1/knowledge-review/* 의 서버 DTO. 필드는 응답 그대로 snake_case다.
 * 원천은 backend/catchup/server/knowledge_review/{api,schemas}.py다.
 */

import type { WikiLayoutItemDto, WikiOwnerDto } from './wikiDto';

/** 큐 한 줄이 가리키는 문서. 미분류 문서는 channel_id·folder_id가 둘 다 null이다 */
export interface ReviewArtifactRefDto {
  id: string;
  title: string | null;
  channel_id: string | null;
  folder_id: string | null;
}

/** origin은 변경안 출처("compiled"·"manual" 등)이고 status는 제안 판정이다 — 둘은 다른 축이다 */
export interface ReviewQueueItemDto {
  proposal_id: string;
  status: string;
  artifact: ReviewArtifactRefDto;
  summary: string;
  origin: string;
  contains_conflict: boolean;
  created_at: string;
  owners: WikiOwnerDto[];
  can_review: boolean;
}

export interface ReviewQueuePageDto {
  items: ReviewQueueItemDto[];
  total: number;
  limit: number;
  offset: number;
}

/** citation_verified는 3값이다 — true 검증, false 대조 실패, null 근거 없음 */
export interface ReviewBlockSourceDto {
  claim_id: string;
  statement: string;
  observed_at: string;
  citation_verified: boolean | null;
}

export interface ReviewVariantDto {
  claim_id: string;
  body: string;
  sources: ReviewBlockSourceDto[];
}

export interface ReviewBlockVerdictDto {
  proposal_id: string;
  block_index: number;
  block_content_hash: string;
  verdict: string;
  rejection_reason: string | null;
  chosen_winner_claim_id: string | null;
  reviewer: string;
  reviewed_at: string;
}

/** variants는 다툼 블록에서만 배열이다 — null("다툼 아님")과 빈 배열은 뜻이 다르다 */
export interface ReviewBlockDto {
  block_index: number;
  block_kind: string;
  heading: string;
  body: string;
  claim_ids: string[];
  proposal_ids: string[];
  ontology_version: string | null;
  block_content_hash: string;
  narrative: string | null;
  relation_ids: string[];
  sources: ReviewBlockSourceDto[];
  variants: ReviewVariantDto[] | null;
  verdict: ReviewBlockVerdictDto | null;
  markdown: string;
  change_reason: string | null;
}

/** 발행판 블록. 결정을 내릴 자리가 없어 block_content_hash·verdict가 실리지 않는다 */
export interface ReviewBaseBlockDto {
  block_index: number;
  block_kind: string;
  heading: string;
  body: string;
  narrative: string | null;
  claim_ids: string[];
  relation_ids: string[];
  sources: ReviewBlockSourceDto[];
}

/** added는 base_block_index가, removed는 block_index가 null이다 */
export interface ReviewBlockChangeDto {
  change: 'added' | 'modified' | 'removed';
  block_index: number | null;
  base_block_index: number | null;
}

export interface ReviewReadSetDto {
  claim_ids: string[];
  proposal_ids: string[];
  relation_ids: string[];
}

export interface ReviewConflictValueDto {
  claim_id: string;
  value: unknown;
  statement: string | null;
}

export interface ReviewConflictDto {
  proposal_id: string;
  predicate: string;
  summary: string;
  values: ReviewConflictValueDto[];
}

/** contains_conflict가 true인데 conflicts가 빌 수 있다 — 그 안건이 이미 판정된 경우다 */
export interface ReviewProposalDetailDto {
  proposal_id: string;
  status: string;
  artifact: ReviewArtifactRefDto;
  origin: string;
  created_at: string;
  base_revision_id: string | null;
  contains_conflict: boolean;
  owners: WikiOwnerDto[];
  can_review: boolean;
  blocks: ReviewBlockDto[];
  /** blocks의 표시 순서·이름. 블록 배열은 재배치되지 않는다 — 구서버 응답에는 없다 */
  layout?: WikiLayoutItemDto[];
  base_blocks: ReviewBaseBlockDto[];
  /** base_blocks의 같은 양식. 발행판이 없으면 빈 목록이다 */
  base_layout?: WikiLayoutItemDto[];
  block_changes: ReviewBlockChangeDto[];
  read_set: ReviewReadSetDto;
  conflicts: ReviewConflictDto[];
}

export interface ReviewPublishDto {
  proposal_id: string;
  verdict: string;
  revision_id: string | null;
  revision_number: number | null;
  blocks_published: number;
  blocks_rejected: number;
  contradictions_resolved: number;
  claims_accepted: number;
}

/** channel_id·owner_user_id는 문서 쪽 조건이고, 서버가 문서 id 집합으로 옮겨 거른다 */
export interface ReviewQueueParams {
  contains_conflict?: boolean;
  channel_id?: string;
  owner_user_id?: number;
  created_after?: string;
  created_before?: string;
  /** 1~200. 기본 50 */
  limit?: number;
  offset?: number;
}

/** block_content_hash는 검토자가 화면에서 본 본문의 지문이며 필수다 */
export interface ReviewBlockVerdictRequest {
  verdict: 'approved' | 'rejected';
  rejection_reason?: string | null;
  chosen_winner_claim_id?: string | null;
  block_content_hash: string;
}

/** base_revision_id는 키가 필수이고 null이 "아직 판이 없는 문서"라는 뜻이다 */
export interface ReviewPublishRequest {
  base_revision_id: string | null;
  undecided?: 'approve' | 'reject' | null;
  rejection_reason?: string | null;
}
