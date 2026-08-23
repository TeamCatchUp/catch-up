import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  mapWikiArtifactDocument,
  mapWikiDocumentBlock,
  mapWikiLayout,
  resolveDocumentBlockText,
} from './wikiDocumentMappers';
import type { WikiArtifactDocumentDto, WikiDocumentBlockDto } from './wikiDto';

const NOW = new Date('2026-08-19T12:00:00.000Z');

const block = (overrides: Partial<WikiDocumentBlockDto> = {}): WikiDocumentBlockDto => ({
  block_index: 0,
  block_kind: 'summary',
  heading: '현황',
  narrative: '8월 들어 결제 실패가 3.2%까지 올랐다.',
  body: 'failure_rate = 3.2%',
  claim_ids: ['c_1'],
  relation_ids: ['r_1'],
  sources: [
    {
      claim_id: 'c_1',
      statement: 'PG사 응답 지연으로 승인 실패가 늘었습니다.',
      observed_at: '2026-08-18T09:00:00Z',
      citation_verified: true,
    },
  ],
  ...overrides,
});

const document = (overrides: Partial<WikiArtifactDocumentDto> = {}): WikiArtifactDocumentDto => ({
  artifact_id: 'af-1',
  channel_id: 'ch-1',
  definition_id: 'def-1',
  kind: 'incident_guide',
  title: '결제 실패 대응 가이드',
  folder_id: 'fd-1',
  owners: [{ user_id: 7, display_name: '팀원F', profile_image_url: null }],
  is_favorite: true,
  revision_id: 'rv-9',
  published_at: '2026-08-19T09:00:00Z',
  last_edited_by: { user_id: 7, display_name: '팀원F', profile_image_url: null },
  last_edited_at: '2026-08-19T09:00:00Z',
  blocks: [block()],
  ...overrides,
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('mapWikiDocumentBlock', () => {
  it('snake_case 블록을 도메인 블록으로 옮긴다', () => {
    expect(mapWikiDocumentBlock(block())).toEqual({
      blockIndex: 0,
      kind: 'summary',
      heading: '현황',
      narrative: '8월 들어 결제 실패가 3.2%까지 올랐다.',
      body: 'failure_rate = 3.2%',
      claimIds: ['c_1'],
      relationIds: ['r_1'],
      sources: [
        {
          claimId: 'c_1',
          statement: 'PG사 응답 지연으로 승인 실패가 늘었습니다.',
          observedAt: '2026-08-18T09:00:00Z',
          citationVerified: true,
        },
      ],
    });
  });

  it('근거가 0건인 블록도 그대로 옮긴다 — 사람이 쓴 블록의 정상 상태다', () => {
    expect(mapWikiDocumentBlock(block({ sources: [] })).sources).toEqual([]);
  });
});

describe('resolveDocumentBlockText', () => {
  it('산문이 있으면 산문이 정본이다', () => {
    const mapped = mapWikiDocumentBlock(block());
    expect(resolveDocumentBlockText(mapped)).toBe('8월 들어 결제 실패가 3.2%까지 올랐다.');
  });

  it('산문이 없으면 값 표기로 폴백한다 — 산문이 없던 옛 판도 읽혀야 한다', () => {
    const mapped = mapWikiDocumentBlock(block({ narrative: null }));
    expect(resolveDocumentBlockText(mapped)).toBe('failure_rate = 3.2%');
  });

  it('산문이 빈 문자열이면 그 빈 문자열이 정본이다 — null만 없음이다', () => {
    const mapped = mapWikiDocumentBlock(block({ narrative: '' }));
    expect(resolveDocumentBlockText(mapped)).toBe('');
  });
});

describe('mapWikiLayout', () => {
  it('block 항목은 blocks[] 자리를 그대로 들고 온다 — 재번호가 없다', () => {
    expect(mapWikiLayout([{ item_kind: 'block', heading: '한 줄 요약', block_index: 3 }])).toEqual([
      { kind: 'block', heading: '한 줄 요약', blockIndex: 3 },
    ]);
  });

  it('block_index 0도 자리다 — 없음과 섞이면 첫 블록이 사라진다', () => {
    expect(mapWikiLayout([{ item_kind: 'block', heading: '요청 상태', block_index: 0 }])).toHaveLength(1);
  });

  it('table 항목은 자리 목록과 행을 같은 순서로 옮긴다', () => {
    expect(
      mapWikiLayout([
        {
          item_kind: 'table',
          heading: '사용 상황',
          block_indexes: [5, 6],
          rows: [
            { label: '사용 상황', value: '월말 정산 때 쓴다.' },
            { label: '요청자 역할', value: '재무 담당자가 요청했다.' },
          ],
        },
      ]),
    ).toEqual([
      {
        kind: 'table',
        heading: '사용 상황',
        blockIndexes: [5, 6],
        rows: [
          { label: '사용 상황', value: '월말 정산 때 쓴다.' },
          { label: '요청자 역할', value: '재무 담당자가 요청했다.' },
        ],
      },
    ]);
  });

  it('placeholder 항목은 가리킬 블록 없이 문구만 갖는다', () => {
    expect(mapWikiLayout([{ item_kind: 'placeholder', heading: '우회 방법', text: '없음' }])).toEqual([
      { kind: 'placeholder', heading: '우회 방법', text: '없음' },
    ]);
  });

  it('모르는 item_kind는 그릴 방법이 없어 떨군다 — 종류가 늘어도 화면이 깨지지 않는다', () => {
    expect(mapWikiLayout([{ item_kind: 'timeline', heading: '연표' }])).toEqual([]);
  });

  it('가리킬 자리가 없는 block 항목도 떨군다', () => {
    expect(mapWikiLayout([{ item_kind: 'block', heading: '요청 상태', block_index: null }])).toEqual([]);
  });

  it('키가 없으면 빈 목록이다 — layout을 싣지 않는 구서버 응답이 그렇다', () => {
    expect(mapWikiLayout(undefined)).toEqual([]);
  });
});

describe('mapWikiArtifactDocument', () => {
  it('문서 상세를 도메인 계약으로 옮긴다', () => {
    const mapped = mapWikiArtifactDocument(document());

    expect(mapped.artifactId).toBe('af-1');
    expect(mapped.channelId).toBe('ch-1');
    expect(mapped.folderId).toBe('fd-1');
    expect(mapped.revisionId).toBe('rv-9');
    expect(mapped.isFavorite).toBe(true);
    expect(mapped.owners).toEqual([{ userId: 7, displayName: '팀원F', profileImageUrl: null }]);
    expect(mapped.blocks).toHaveLength(1);
  });

  it('발행 시각은 ISO와 표시 문자열을 함께 준다 — 상대 표기는 정렬에 쓸 수 없다', () => {
    const mapped = mapWikiArtifactDocument(document());

    expect(mapped.publishedAt).toBe('2026-08-19T09:00:00Z');
    expect(mapped.publishedLabel).toBe('3시간 전');
  });

  it('채널·폴더가 없는 문서도 옮긴다 — 경로 마디가 비는 것이 정상이다', () => {
    const mapped = mapWikiArtifactDocument(document({ channel_id: null, folder_id: null }));

    expect(mapped.channelId).toBeNull();
    expect(mapped.folderId).toBeNull();
  });

  it('layout이 없는 응답은 빈 목록으로 온다 — 구서버에서도 blocks 순서로 읽힌다', () => {
    expect(mapWikiArtifactDocument(document()).layout).toEqual([]);
  });

  it('layout이 오면 그대로 싣고 blocks는 건드리지 않는다', () => {
    const mapped = mapWikiArtifactDocument(
      document({
        blocks: [block(), block({ block_index: 1, heading: '요청 상태' })],
        layout: [
          { item_kind: 'block', heading: '요청 상태', block_index: 1 },
          { item_kind: 'block', heading: '한 줄 요약', block_index: 0 },
        ],
      }),
    );

    expect(mapped.layout).toEqual([
      { kind: 'block', heading: '요청 상태', blockIndex: 1 },
      { kind: 'block', heading: '한 줄 요약', blockIndex: 0 },
    ]);
    expect(mapped.blocks.map((item) => item.blockIndex)).toEqual([0, 1]);
  });
});
