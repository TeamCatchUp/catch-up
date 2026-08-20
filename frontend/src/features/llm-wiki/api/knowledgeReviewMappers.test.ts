import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ReviewBaseBlockDto, ReviewBlockDto, ReviewQueueItemDto } from './knowledgeReviewDto';
import {
  mapChangeProposalStatus,
  mapReviewBaseBlock,
  mapReviewBlock,
  mapReviewQueueItem,
} from './knowledgeReviewMappers';

const NOW = new Date('2026-08-19T12:00:00.000Z');

const source = {
  claim_id: 'cl-1',
  statement: '8월 결제 실패율은 2.1%다.',
  observed_at: '2026-08-18T02:00:00Z',
  citation_verified: true,
};

const block = (overrides: Partial<ReviewBlockDto> = {}): ReviewBlockDto => ({
  block_index: 0,
  block_kind: 'fact_section',
  heading: '현황',
  body: '결제 실패율 2.1%',
  claim_ids: ['cl-1'],
  proposal_ids: ['pr-1'],
  ontology_version: 'v3',
  block_content_hash: 'hash-0',
  narrative: '8월 들어 결제 실패가 늘었다.',
  relation_ids: [],
  sources: [source],
  variants: null,
  verdict: null,
  markdown: '## 현황\n8월 들어 결제 실패가 늘었다.',
  change_reason: '수치 갱신',
  ...overrides,
});

const baseBlock = (overrides: Partial<ReviewBaseBlockDto> = {}): ReviewBaseBlockDto => ({
  block_index: 0,
  block_kind: 'fact_section',
  heading: '현황',
  body: '결제 실패율 1.4%',
  narrative: null,
  claim_ids: ['cl-1'],
  relation_ids: [],
  sources: [source],
  ...overrides,
});

const queueItem = (overrides: Partial<ReviewQueueItemDto> = {}): ReviewQueueItemDto => ({
  proposal_id: 'pr-1',
  status: 'pending',
  artifact: { id: 'af-1', title: '결제 실패 대응 가이드', channel_id: 'ch-1', folder_id: 'fd-1' },
  summary: '현황 블록 수치 갱신',
  origin: 'compiled',
  contains_conflict: false,
  created_at: '2026-08-19T09:00:00Z',
  owners: [{ user_id: 7, display_name: '팀원F', profile_image_url: null }],
  can_review: true,
  ...overrides,
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('mapReviewBlock', () => {
  it('블록 본문·근거·지문을 camelCase로 옮긴다', () => {
    const mapped = mapReviewBlock(block());

    expect(mapped).toMatchObject({
      blockIndex: 0,
      kind: 'fact_section',
      heading: '현황',
      narrative: '8월 들어 결제 실패가 늘었다.',
      claimIds: ['cl-1'],
      proposalIds: ['pr-1'],
      ontologyVersion: 'v3',
      blockContentHash: 'hash-0',
      variants: null,
      verdict: null,
    });
    expect(mapped.sources).toEqual([
      { claimId: 'cl-1', statement: source.statement, observedAt: source.observed_at, citationVerified: true },
    ]);
  });

  it('change_reason을 reason으로 옮긴다', () => {
    expect(mapReviewBlock(block()).reason).toBe('수치 갱신');
    expect(mapReviewBlock(block({ change_reason: null })).reason).toBeNull();
  });

  it('다툼 블록의 후보 배열을 옮기고 null과 구별한다', () => {
    const contested = mapReviewBlock(
      block({
        block_kind: 'contested',
        sources: [],
        variants: [{ claim_id: 'cl-2', body: '2.1%', sources: [source] }],
      }),
    );

    expect(contested.variants).toEqual([
      {
        claimId: 'cl-2',
        body: '2.1%',
        sources: [
          { claimId: 'cl-1', statement: source.statement, observedAt: source.observed_at, citationVerified: true },
        ],
      },
    ]);
    expect(mapReviewBlock(block()).variants).toBeNull();
  });

  it('저장된 결정이 있으면 그대로 옮긴다', () => {
    const decided = mapReviewBlock(
      block({
        verdict: {
          proposal_id: 'pr-1',
          block_index: 0,
          block_content_hash: 'hash-0',
          verdict: 'rejected',
          rejection_reason: '근거 부족',
          chosen_winner_claim_id: null,
          reviewer: '팀원F',
          reviewed_at: '2026-08-19T10:00:00Z',
        },
      }),
    );

    expect(decided.verdict).toEqual({
      proposalId: 'pr-1',
      blockIndex: 0,
      blockContentHash: 'hash-0',
      verdict: 'rejected',
      rejectionReason: '근거 부족',
      chosenWinnerClaimId: null,
      reviewer: '팀원F',
      reviewedAt: '2026-08-19T10:00:00Z',
    });
  });
});

describe('mapReviewBaseBlock', () => {
  it('결정 자리가 없는 발행판 블록은 빈 지문과 null 판정으로 온다', () => {
    const mapped = mapReviewBaseBlock(baseBlock());

    expect(mapped.blockContentHash).toBe('');
    expect(mapped.verdict).toBeNull();
    expect(mapped.variants).toBeNull();
    expect(mapped.proposalIds).toEqual([]);
    expect(mapped.claimIds).toEqual(['cl-1']);
  });
});

describe('mapChangeProposalStatus', () => {
  it('닫힌 집합의 값은 그대로 통과시킨다', () => {
    expect(mapChangeProposalStatus('approved')).toBe('approved');
    expect(mapChangeProposalStatus('abandoned')).toBe('abandoned');
  });

  it('집합 밖의 값은 계류로 읽는다', () => {
    expect(mapChangeProposalStatus('banana')).toBe('pending');
  });
});

describe('mapReviewQueueItem', () => {
  it('큐 한 줄을 목록 행으로 옮긴다', () => {
    expect(mapReviewQueueItem(queueItem())).toEqual({
      id: 'pr-1',
      type: 'compiled',
      title: '결제 실패 대응 가이드',
      waitingLabel: '3시간 전',
      status: 'pending',
      rejectionReason: null,
      hasConflictIcon: false,
      canReview: true,
    });
  });

  it('문서 제목이 없으면 요약으로 물러난다', () => {
    expect(mapReviewQueueItem(queueItem({ artifact: { ...queueItem().artifact, title: null } })).title).toBe(
      '현황 블록 수치 갱신',
    );
  });

  it('다툼 블록이 있는 변경안은 충돌 표식을 켠다', () => {
    expect(mapReviewQueueItem(queueItem({ contains_conflict: true })).hasConflictIcon).toBe(true);
  });
});
