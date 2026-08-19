import { describe, expect, it } from 'vitest';

import type { WikiArtifactListItemDto, WikiChannelListItemDto } from '../api/wikiDto';
import { buildWikiChannelAdmins, buildWikiFavorites, buildWikiNavTree } from './wikiNavTree';

const channel = (overrides?: Partial<WikiChannelListItemDto>): WikiChannelListItemDto => ({
  id: 'ch-1',
  name: '결제',
  workspace_id: 1,
  is_admin: true,
  document_count: 2,
  folders: [{ id: 'fd-1', name: '환불', channel_id: 'ch-1' }],
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
