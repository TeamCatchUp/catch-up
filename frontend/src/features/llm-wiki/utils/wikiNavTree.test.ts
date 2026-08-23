import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WikiArtifactListItemDto, WikiChannelListItemDto } from '../api/wikiDto';
import { buildDocumentMetaLines, buildWikiChannelAdmins, buildWikiFavorites, buildWikiNavTree } from './wikiNavTree';

const channel = (overrides?: Partial<WikiChannelListItemDto>): WikiChannelListItemDto => ({
  id: 'ch-1',
  name: '결제',
  workspace_id: 1,
  is_admin: true,
  document_count: 2,
  folders: [
    {
      id: 'fd-1',
      name: '환불',
      channel_id: 'ch-1',
      created_at: '2026-07-20T00:00:00Z',
      created_by: null,
      last_activity_at: null,
    },
  ],
  purpose_presets: [],
  definitions: [],
  ...overrides,
});

const artifact = (overrides?: Partial<WikiArtifactListItemDto>): WikiArtifactListItemDto => ({
  artifact_id: 'ar-1',
  kind: 'policy',
  title: '결제 실패 대응',
  channel_id: 'ch-1',
  folder_id: null,
  created_at: '2026-08-01T00:00:00Z',
  last_activity_at: '2026-08-02T00:00:00Z',
  status: 'published',
  pending_proposal_count: 0,
  latest_revision: null,
  owners: [],
  is_favorite: false,
  last_edited_by: { user_id: 7, display_name: '팀원F', profile_image_url: null },
  last_edited_at: '2026-08-19T09:00:00Z',
  ...overrides,
});

describe('buildWikiNavTree', () => {
  it('문서를 받아오기 전에는 채널 아래에 폴더만 선다', () => {
    const [node] = buildWikiNavTree([channel()], new Map());

    expect(node.id).toBe('ch-1');
    expect(node.href).toBe('/llm-wiki/channel/ch-1');
    expect(node.children).toHaveLength(1);
    expect(node.children?.[0]).toMatchObject({ id: 'fd-1', kind: 'folder', href: '/llm-wiki/folder/fd-1' });
    // 자식이 없는 폴더는 undefined다 — NavTree가 빈 자식으로 캐럿을 그리지 않게 한다
    expect(node.children?.[0].children).toBeUndefined();
  });

  it('한 채널 응답이 폴더 문서와 채널 루트 문서를 함께 나눠 담는다', () => {
    const documents = [artifact(), artifact({ artifact_id: 'ar-2', title: '환불 기준', folder_id: 'fd-1' })];
    const [node] = buildWikiNavTree([channel()], new Map([['ch-1', documents]]));

    const [folder, root] = node.children ?? [];
    expect(folder.children?.map((child) => child.id)).toEqual(['ar-2']);
    expect(root).toMatchObject({ id: 'ar-1', kind: 'document', href: '/llm-wiki/ar-1' });
  });

  it('펼치지 않은 채널에는 문서가 붙지 않는다', () => {
    const nodes = buildWikiNavTree(
      [channel(), channel({ id: 'ch-2', name: '정산', folders: [] })],
      new Map([['ch-1', [artifact()]]]),
    );

    expect(nodes[0].children).toHaveLength(2);
    expect(nodes[1].children).toBeUndefined();
  });
});

describe('buildDocumentMetaLines', () => {
  const NOW = new Date('2026-08-19T12:00:00.000Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('최종 편집자와 시각을 케밥 메타 2줄로 만든다', () => {
    expect(buildDocumentMetaLines(artifact())).toEqual(['팀원F 최종 편집', '3시간 전']);
  });

  it('승인자가 사용자로 이어지지 않으면 시각 줄만 남는다', () => {
    expect(buildDocumentMetaLines(artifact({ last_edited_by: null }))).toEqual(['3시간 전']);
  });

  it('발행판이 없으면 줄 자체를 만들지 않는다 — 케밥 구분선까지 함께 빠진다', () => {
    expect(buildDocumentMetaLines(artifact({ last_edited_by: null, last_edited_at: null }))).toBeUndefined();
  });

  // 키를 싣지 않는 구서버 응답. undefined를 시각으로 읽으면 "NaN일 전"이 케밥에 나간다
  it('시각 키가 아예 없는 응답도 줄을 만들지 않는다', () => {
    expect(buildDocumentMetaLines(artifact({ last_edited_by: null, last_edited_at: undefined }))).toBeUndefined();
  });

  it('트리 문서 노드가 그 메타를 들고 선다', () => {
    const [node] = buildWikiNavTree([channel()], new Map([['ch-1', [artifact()]]]));

    expect(node.children?.[1].metaLines).toEqual(['팀원F 최종 편집', '3시간 전']);
  });
});

describe('buildWikiChannelAdmins·buildWikiFavorites', () => {
  it('채널별 관리자 판정을 맵으로 편다', () => {
    expect(buildWikiChannelAdmins([channel(), channel({ id: 'ch-2', is_admin: false })])).toEqual({
      'ch-1': true,
      'ch-2': false,
    });
  });

  it('즐겨찾기는 문서 경로를 목적지로 갖는다', () => {
    const favorites = buildWikiFavorites([
      { artifact_id: 'ar-1', title: '결제 실패 대응', kind: 'policy', channel_id: 'ch-1', folder_id: null, favorited_at: '2026-08-02T00:00:00Z' },
    ]);

    expect(favorites).toEqual([{ id: 'ar-1', label: '결제 실패 대응', href: '/llm-wiki/ar-1' }]);
  });
});
