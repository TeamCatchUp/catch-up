import { describe, expect, it } from 'vitest';

import {
  BASE_WIKI_BLOCKS,
  PROPOSED_WIKI_BLOCKS,
  reviewProposalDetail,
  withBlockVerdict,
} from '../../../fixtures/llmWikiDiffFixtures';
import { composeProposalPreview } from './composeProposalPreview';

/** 0번은 modified(발행판에 짝이 있음), 1번은 added(되돌릴 자리가 없음) */
const [MODIFIED, ADDED] = PROPOSED_WIKI_BLOCKS;

const headings = (items: ReturnType<typeof composeProposalPreview>) =>
  items.flatMap((item) => {
    if (item.kind === 'details') return item.rows.map((row) => row.heading);
    if (item.kind === 'timeline') return item.items.map((timelineItem) => timelineItem.heading);
    return [item.heading];
  });

describe('composeProposalPreview', () => {
  it('판정이 없으면 제안 블록을 양식 순서대로 낸다', () => {
    const items = composeProposalPreview(reviewProposalDetail());

    expect(headings(items)).toEqual(['PG 점검 시간 예외', '재시도 정책']);
    expect(items[1]).toMatchObject({ kind: 'section', text: MODIFIED.narrative });
  });

  it('승인된 블록은 제안 블록 그대로다', () => {
    const items = composeProposalPreview(
      reviewProposalDetail({ blocks: [withBlockVerdict(MODIFIED, 'approved'), ADDED] }),
    );

    expect(items[1]).toMatchObject({ text: MODIFIED.narrative });
  });

  it('반려된 블록은 발행판 본문으로 되돌아간다', () => {
    const items = composeProposalPreview(
      reviewProposalDetail({ blocks: [withBlockVerdict(MODIFIED, 'rejected'), ADDED] }),
    );

    // 양식이 정한 제목 자리는 그대로 두고 본문만 발행판 것으로 바뀐다
    expect(items[1]).toMatchObject({ heading: '재시도 정책', text: BASE_WIKI_BLOCKS[0].narrative });
  });

  it('반려된 신규 블록은 되돌릴 자리가 없어 빠진다', () => {
    const items = composeProposalPreview(
      reviewProposalDetail({ blocks: [MODIFIED, withBlockVerdict(ADDED, 'rejected')] }),
    );

    expect(headings(items)).toEqual(['재시도 정책']);
  });

  it('양식이 비면 블록 순서가 표시 순서다', () => {
    const items = composeProposalPreview(reviewProposalDetail({ layout: [] }));

    expect(headings(items)).toEqual(['재시도 정책', 'PG 점검 시간 예외']);
  });

  it('발행판이 없는 신규 문서도 제안 블록을 그대로 낸다', () => {
    const items = composeProposalPreview(
      reviewProposalDetail({
        baseRevisionId: null,
        baseBlocks: [],
        changes: [
          { kind: 'added', blockIndex: 0, baseBlockIndex: null },
          { kind: 'added', blockIndex: 1, baseBlockIndex: null },
        ],
      }),
    );

    expect(headings(items)).toEqual(['PG 점검 시간 예외', '재시도 정책']);
  });

  it('자리표시 항목은 그대로 남는다 — 값이 없다는 사실도 문서의 일부다', () => {
    const items = composeProposalPreview(
      reviewProposalDetail({ layout: [{ kind: 'placeholder', heading: '결정 사항', text: '없음' }] }),
    );

    expect(items).toEqual([{ kind: 'section', heading: '결정 사항', text: '없음' }]);
  });
});
