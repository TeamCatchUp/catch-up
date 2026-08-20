/** 변경안 상세 DTO → 화면 계약. 블록 변환은 knowledgeReviewMappers의 것을 그대로 쓴다. */

import type { BlockChange, WikiBlock } from '../types/llmWikiDiff';
import type { ChangeProposalStatus, DocumentOwner } from '../types/llmWikiModel';
import type { ReviewBlockChangeDto, ReviewProposalDetailDto } from './knowledgeReviewDto';
import { mapChangeProposalStatus, mapReviewBaseBlock, mapReviewBlock } from './knowledgeReviewMappers';
import { mapWikiOwners } from './wikiMappers';

/**
 * 검토 상세 화면이 쓰는 값만 옮긴다. read_set·conflicts는 소비처가 없어 두지 않는다 —
 * 다툼 블록 카드는 시안 게이트다.
 */
export interface ReviewProposalDetailData {
  proposalId: string;
  artifactId: string;
  /** 제목 없는 문서가 있다. 목록 행은 summary로 폴백하지만 상세에는 그 자리가 없다 */
  title: string | null;
  channelId: string | null;
  folderId: string | null;
  status: ChangeProposalStatus;
  /** [BE] 결정 권한. 목록 행 값이 아니라 이쪽이 이 화면의 정본이다 */
  canReview: boolean;
  /** [BE] 발행 요청에 그대로 실린다. null은 "아직 판이 없는 문서"라 생략과 다르다 */
  baseRevisionId: string | null;
  owners: DocumentOwner[];
  blocks: WikiBlock[];
  baseBlocks: WikiBlock[];
  changes: BlockChange[];
}

export function mapReviewBlockChange(dto: ReviewBlockChangeDto): BlockChange {
  return { kind: dto.change, blockIndex: dto.block_index, baseBlockIndex: dto.base_block_index };
}

export function mapReviewProposalDetail(dto: ReviewProposalDetailDto): ReviewProposalDetailData {
  return {
    proposalId: dto.proposal_id,
    artifactId: dto.artifact.id,
    title: dto.artifact.title,
    channelId: dto.artifact.channel_id,
    folderId: dto.artifact.folder_id,
    status: mapChangeProposalStatus(dto.status),
    canReview: dto.can_review,
    baseRevisionId: dto.base_revision_id,
    owners: mapWikiOwners(dto.owners),
    blocks: dto.blocks.map(mapReviewBlock),
    baseBlocks: dto.base_blocks.map(mapReviewBaseBlock),
    changes: dto.block_changes.map(mapReviewBlockChange),
  };
}
