import type { BlockChange, WikiBlock } from '../types/llmWikiDiff';

/**
 * diff 뷰 스토리용 base/proposed blocks[] 쌍. 백엔드 BlockResponse 형태를 따른다.
 * 기존 llmWikiFixtures와 분리한 이유는 이쪽이 blocks[] 계약이라 성격이 다르기 때문이다.
 */

/** 본문에서 파생하는 가짜 지문. 같은 본문이면 같은 값이어야 낙관적 잠금 mock이 성립한다 */
function fakeContentHash(body: string): string {
  let hash = 5381;
  for (const char of body) hash = ((hash << 5) + hash + char.codePointAt(0)!) >>> 0;
  return `sha256:fixture-${hash.toString(16)}`;
}

type BlockSeed = Partial<WikiBlock> & Pick<WikiBlock, 'blockIndex' | 'heading' | 'body' | 'claimIds'>;

/** 서버가 채우는 필드를 기본값으로 메운다. blockIndex는 배열 자리와 맞춰 호출부에서 준다 */
function block(seed: BlockSeed): WikiBlock {
  return {
    kind: 'claim_section',
    // narrative 기본값 null = 산문 없는 옛 데이터 표본. 있는 표본은 호출부가 명시로 준다
    narrative: null,
    proposalIds: ['prop-payment-retry'],
    ontologyVersion: 'v1',
    blockContentHash: fakeContentHash(seed.body),
    sources: [],
    variants: null,
    verdict: null,
    ...seed,
  };
}

export const BASE_WIKI_BLOCKS: readonly WikiBlock[] = [
  block({
    blockIndex: 0,
    heading: '재시도 정책',
    body: '결제 승인 실패 시 1회 재시도한다.\n재시도 간격은 30초다.',
    narrative: '결제 승인이 실패하면 자동으로 한 번 더 시도합니다.\n재시도 간격은 30초입니다.',
    claimIds: ['c-retry-1'],
  }),
  block({
    blockIndex: 1,
    heading: '수동 재시도 안내',
    body: '자동 재시도가 모두 실패하면 상담원이 수동 재시도를 안내한다.',
    claimIds: ['c-manual-1'],
  }),
];

export const PROPOSED_WIKI_BLOCKS: readonly WikiBlock[] = [
  block({
    blockIndex: 0,
    heading: '재시도 정책',
    body: '결제 승인 실패 시 3회까지 재시도한다.\n재시도 간격은 30초다.',
    narrative: '결제 승인이 실패하면 자동으로 세 번까지 시도합니다.\n재시도 간격은 30초입니다.',
    claimIds: ['c-retry-1'],
    sources: [
      {
        claimId: 'c-retry-1',
        statement: '재시도는 최대 3회까지 수행한다.',
        observedAt: '2026-08-03T04:12:00Z',
        citationVerified: true,
      },
    ],
    reason: '근거 1건 추가·0건 폐기',
  }),
  block({
    blockIndex: 1,
    heading: 'PG 점검 시간 예외',
    body: 'PG사 정기 점검 시간에는 재시도를 수행하지 않는다.',
    claimIds: ['c-pg-1'],
    sources: [
      {
        claimId: 'c-pg-1',
        statement: '점검 시간대에는 승인 요청이 전부 실패한다.',
        observedAt: '2026-08-05T21:40:00Z',
        citationVerified: null,
      },
    ],
    reason: '새 섹션',
  }),
];

/**
 * 기본 쌍의 변경 목록. 서버가 짝짓기를 마친 결과 모양이다 —
 * 빠진 블록은 변경안에 자리가 없어 blockIndex가 null이고 사유도 붙지 않는다.
 */
export const PROPOSED_BLOCK_CHANGES: readonly BlockChange[] = [
  { kind: 'modified', blockIndex: 0, baseBlockIndex: 0 },
  { kind: 'added', blockIndex: 1, baseBlockIndex: null },
  { kind: 'removed', blockIndex: null, baseBlockIndex: 1 },
];

/** 다툼 블록 — sources를 비우고 variants에만 근거를 싣는 계약을 표본으로 남긴다 */
export const CONTESTED_PROPOSED_BLOCKS: readonly WikiBlock[] = [
  block({
    blockIndex: 0,
    heading: '재시도 정책',
    body: '결제 승인 실패 시 3회까지 재시도한다.\n재시도 간격은 30초다.',
    claimIds: ['c-retry-1', 'c-retry-2'],
    variants: [
      {
        claimId: 'c-retry-1',
        body: '결제 승인 실패 시 3회까지 재시도한다.',
        sources: [
          {
            claimId: 'c-retry-1',
            statement: '재시도는 최대 3회까지 수행한다.',
            observedAt: '2026-08-03T04:12:00Z',
            citationVerified: true,
          },
        ],
      },
      {
        claimId: 'c-retry-2',
        body: '결제 승인 실패 시 5회까지 재시도한다.',
        sources: [
          {
            claimId: 'c-retry-2',
            statement: '재시도 상한을 5회로 올렸다는 상담 답변이 있었다.',
            observedAt: '2026-08-06T02:05:00Z',
            citationVerified: false,
          },
        ],
      },
    ],
    reason: '근거 1건 추가·0건 폐기',
  }),
];

/** 이미 반려 판정이 저장된 블록 */
export const JUDGED_PROPOSED_BLOCKS: readonly WikiBlock[] = [
  block({
    blockIndex: 0,
    heading: '재시도 정책',
    body: '결제 승인 실패 시 3회까지 재시도한다.\n재시도 간격은 30초다.',
    claimIds: ['c-retry-1'],
    reason: '산문 갱신',
    verdict: {
      proposalId: 'prop-payment-retry',
      blockIndex: 0,
      blockContentHash: fakeContentHash('결제 승인 실패 시 3회까지 재시도한다.\n재시도 간격은 30초다.'),
      verdict: 'rejected',
      rejectionReason: '근거 VOC가 동일 고객사 3건이라 일반화하기 이르다',
      chosenWinnerClaimId: null,
      reviewer: '직원10',
      reviewedAt: '2026-08-10T01:20:00Z',
    },
  }),
];

/**
 * 판정이 절반 진행된 변경안 — 0번은 승인, 1번은 반려.
 * 승인 판정은 카드에 대응 표시가 없어 미판정과 같은 모습으로 남는다.
 */
export const PARTIALLY_JUDGED_PROPOSED_BLOCKS: readonly WikiBlock[] = PROPOSED_WIKI_BLOCKS.map(
  (wikiBlock, index): WikiBlock => ({
    ...wikiBlock,
    verdict: {
      proposalId: 'prop-payment-retry',
      blockIndex: wikiBlock.blockIndex,
      blockContentHash: wikiBlock.blockContentHash,
      verdict: index === 0 ? 'approved' : 'rejected',
      rejectionReason: index === 0 ? null : '점검 시간 근거가 한 건뿐이라 더 모으고 싶습니다',
      chosenWinnerClaimId: null,
      reviewer: '직원10',
      reviewedAt: '2026-08-19T02:00:00Z',
    },
  }),
);

/** LongText 스토리용 — 긴 문단에서 자연 줄바꿈·단어 강조가 함께 보이는 쌍 */
export const LONG_BASE_WIKI_BLOCKS: readonly WikiBlock[] = [
  block({
    blockIndex: 0,
    heading: '고객 안내 문구 표준',
    body: '결제 승인이 실패한 경우 고객에게는 결제 수단을 확인해 달라는 안내 문구를 노출하고, 동일 카드로 연속 실패가 발생하면 상담 채널로 연결되는 배너를 함께 보여 준다. 이 문구는 PG사별로 다르게 표기하지 않는다.',
    claimIds: ['c-copy-1'],
  }),
];

export const LONG_PROPOSED_WIKI_BLOCKS: readonly WikiBlock[] = [
  block({
    blockIndex: 0,
    heading: '고객 안내 문구 표준',
    body: '결제 승인이 실패한 경우 고객에게는 결제 수단과 한도를 확인해 달라는 안내 문구를 노출하고, 동일 카드로 두 번 이상 실패가 발생하면 상담 채널로 연결되는 배너를 함께 보여 준다. 이 문구는 PG사별로 다르게 표기하지 않는다.',
    claimIds: ['c-copy-1'],
    reason: '근거 2건 추가·1건 폐기',
  }),
];

/** 한 자리만 바뀐 쌍 — 긴 문단·이미 판정된 블록 스토리가 함께 쓴다 */
export const SINGLE_MODIFIED_BLOCK_CHANGES: readonly BlockChange[] = [
  { kind: 'modified', blockIndex: 0, baseBlockIndex: 0 },
];
