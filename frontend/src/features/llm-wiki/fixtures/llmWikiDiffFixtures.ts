import type { WikiBlock } from '../types/llmWikiDiff';

/**
 * diff 뷰 스토리용 base/proposed blocks[] 쌍.
 *
 * computeBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS)가 정확히
 * modified(재시도 정책) → added(PG 점검 시간 예외) → removed(수동 재시도 안내)
 * 세 카드를 내도록 설계됐다 — 이 불변식은 llmWikiDiffFixtures.test.ts가 지킨다.
 * 기존 llmWikiFixtures.ts와 분리한 이유: 이 파일은 blocks[] 형태라 도메인 mock과 성격이 다르다.
 */
export const BASE_WIKI_BLOCKS: readonly WikiBlock[] = [
  {
    kind: 'claim_section',
    heading: '재시도 정책',
    body: '결제 승인 실패 시 1회 재시도한다.\n재시도 간격은 30초다.',
    claimIds: ['c-retry-1'],
  },
  {
    kind: 'claim_section',
    heading: '수동 재시도 안내',
    body: '자동 재시도가 모두 실패하면 상담원이 수동 재시도를 안내한다.',
    claimIds: ['c-manual-1'],
  },
];

export const PROPOSED_WIKI_BLOCKS: readonly WikiBlock[] = [
  {
    kind: 'claim_section',
    heading: '재시도 정책',
    body: '결제 승인 실패 시 3회까지 재시도한다.\n재시도 간격은 30초다.',
    claimIds: ['c-retry-1'],
    reason: '8월 VOC 3건에서 재시도 횟수를 늘려달라는 요구가 반복 확인됨',
  },
  {
    kind: 'claim_section',
    heading: 'PG 점검 시간 예외',
    body: 'PG사 정기 점검 시간에는 재시도를 수행하지 않는다.',
    claimIds: ['c-pg-1'],
    reason: '점검 시간대 재시도 실패 문의가 신규 근거 VOC로 유입됨',
  },
];

/** LongText 스토리용 — 긴 문단에서 자연 줄바꿈·단어 강조가 함께 보이는 쌍 */
export const LONG_BASE_WIKI_BLOCKS: readonly WikiBlock[] = [
  {
    kind: 'claim_section',
    heading: '고객 안내 문구 표준',
    body: '결제 승인이 실패한 경우 고객에게는 결제 수단을 확인해 달라는 안내 문구를 노출하고, 동일 카드로 연속 실패가 발생하면 상담 채널로 연결되는 배너를 함께 보여 준다. 이 문구는 PG사별로 다르게 표기하지 않는다.',
    claimIds: ['c-copy-1'],
  },
];

export const LONG_PROPOSED_WIKI_BLOCKS: readonly WikiBlock[] = [
  {
    kind: 'claim_section',
    heading: '고객 안내 문구 표준',
    body: '결제 승인이 실패한 경우 고객에게는 결제 수단과 한도를 확인해 달라는 안내 문구를 노출하고, 동일 카드로 두 번 이상 실패가 발생하면 상담 채널로 연결되는 배너를 함께 보여 준다. 이 문구는 PG사별로 다르게 표기하지 않는다.',
    claimIds: ['c-copy-1'],
    reason: '한도 초과 문의가 안내 문구 개선 요구로 반복 유입됨',
  },
];
