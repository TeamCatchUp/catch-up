import { describe, expect, it } from 'vitest';

import { mapReviewProposalDetail } from './knowledgeReviewDetailMappers';
import type { ReviewBlockDto, ReviewProposalDetailDto } from './knowledgeReviewDto';

const block = (overrides: Partial<ReviewBlockDto> = {}): ReviewBlockDto => ({
  block_index: 0,
  block_kind: 'claim_section',
  heading: 'request_status',
  body: '검토 중',
  claim_ids: ['c-1'],
  proposal_ids: ['p-1'],
  ontology_version: 'v1',
  block_content_hash: 'sha256:one',
  narrative: '요청은 검토 중입니다.',
  relation_ids: [],
  sources: [],
  variants: null,
  verdict: null,
  markdown: '## 요청 상태\n요청은 검토 중입니다.',
  change_reason: null,
  ...overrides,
});

const detail = (overrides: Partial<ReviewProposalDetailDto> = {}): ReviewProposalDetailDto => ({
  proposal_id: 'pr-1',
  status: 'pending',
  artifact: { id: 'af-1', title: '요청 현황: 엑셀 내려받기', channel_id: 'ch-1', folder_id: null },
  origin: 'compiled',
  created_at: '2026-08-19T09:00:00Z',
  base_revision_id: 'rv-1',
  contains_conflict: false,
  owners: [],
  can_review: true,
  blocks: [block()],
  base_blocks: [],
  block_changes: [],
  read_set: { claim_ids: [], proposal_ids: [], relation_ids: [] },
  conflicts: [],
  ...overrides,
});

describe('mapReviewProposalDetail', () => {
  it('상세를 화면 계약으로 옮긴다', () => {
    const mapped = mapReviewProposalDetail(detail());

    expect(mapped.proposalId).toBe('pr-1');
    expect(mapped.artifactId).toBe('af-1');
    expect(mapped.baseRevisionId).toBe('rv-1');
    expect(mapped.canReview).toBe(true);
    expect(mapped.blocks).toHaveLength(1);
  });

  it('블록의 change_reason이 카드 사유로 이어진다', () => {
    const mapped = mapReviewProposalDetail(
      detail({ blocks: [block({ change_reason: '근거 1건이 추가되었습니다.' })] }),
    );

    expect(mapped.blocks[0].reason).toBe('근거 1건이 추가되었습니다.');
  });

  it('사유 없는 블록은 없음 그대로다 — 바뀌지 않은 블록과 신규 문서가 그렇다', () => {
    expect(mapReviewProposalDetail(detail()).blocks[0].reason).toBeNull();
  });

  it('layout·base_layout을 옮기고 blocks 자리는 그대로 둔다', () => {
    const mapped = mapReviewProposalDetail(
      detail({
        blocks: [block(), block({ block_index: 1, heading: 'last_reported_at', block_content_hash: 'sha256:two' })],
        layout: [
          { item_kind: 'block', heading: '요청 상태', block_index: 0 },
          { item_kind: 'block', heading: '최근 보고', block_index: 1 },
        ],
        base_blocks: [
          {
            block_index: 0,
            block_kind: 'claim_section',
            heading: 'request_status',
            body: '수집됨',
            narrative: null,
            claim_ids: [],
            relation_ids: [],
            sources: [],
          },
        ],
        base_layout: [{ item_kind: 'block', heading: '요청 상태', block_index: 0 }],
      }),
    );

    expect(mapped.layout).toEqual([
      { kind: 'block', heading: '요청 상태', blockIndex: 0 },
      { kind: 'block', heading: '최근 보고', blockIndex: 1 },
    ]);
    expect(mapped.baseLayout).toEqual([{ kind: 'block', heading: '요청 상태', blockIndex: 0 }]);
    expect(mapped.blocks.map((item) => item.blockIndex)).toEqual([0, 1]);
  });

  it('layout 키가 없으면 빈 목록이다 — 구서버 응답도 그대로 읽힌다', () => {
    const mapped = mapReviewProposalDetail(detail());

    expect(mapped.layout).toEqual([]);
    expect(mapped.baseLayout).toEqual([]);
  });

  it('발행판이 없으면 base_layout도 빈 목록이다', () => {
    const mapped = mapReviewProposalDetail(detail({ base_blocks: [], base_layout: [] }));

    expect(mapped.baseBlocks).toEqual([]);
    expect(mapped.baseLayout).toEqual([]);
  });
});
