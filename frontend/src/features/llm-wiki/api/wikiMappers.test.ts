import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WikiArtifactListItemDto, WikiArtifactListParams, WikiChannelListItemDto, WikiOwnerDto } from './wikiDto';
import {
  createWikiLocationIndex,
  mapDocumentStatus,
  mapWikiArtifactRow,
  mapWikiArtifactRows,
  mapWikiChannelListItem,
  mapWikiMembers,
  mapWikiOwner,
  resolveDocumentBreadcrumbs,
} from './wikiMappers';

const NOW = new Date('2026-08-19T12:00:00.000Z');

const owner = (overrides: Partial<WikiOwnerDto> = {}): WikiOwnerDto => ({
  user_id: 7,
  display_name: '팀원F',
  profile_image_url: 'https://cdn.example.com/7.png',
  ...overrides,
});

const channel = (overrides: Partial<WikiChannelListItemDto> = {}): WikiChannelListItemDto => ({
  id: 'ch-1',
  name: '결제',
  workspace_id: 3,
  is_admin: true,
  document_count: 12,
  folders: [
    {
      id: 'fd-1',
      name: '장애 대응',
      channel_id: 'ch-1',
      created_at: '2026-08-01T00:00:00Z',
      created_by: owner(),
      last_activity_at: '2026-08-19T09:00:00Z',
    },
  ],
  purpose_presets: ['incident'],
  definitions: [{ definition_id: 'def-1', kind: 'incident_guide', folder_id: 'fd-1', purpose_presets: ['incident'] }],
  ...overrides,
});

const artifact = (overrides: Partial<WikiArtifactListItemDto> = {}): WikiArtifactListItemDto => ({
  artifact_id: 'af-1',
  kind: 'incident_guide',
  title: '결제 실패 대응 가이드',
  channel_id: 'ch-1',
  folder_id: 'fd-1',
  created_at: '2026-08-01T00:00:00Z',
  last_activity_at: '2026-08-19T09:00:00Z',
  status: 'published',
  pending_proposal_count: 0,
  latest_revision: { revision_id: 'rv-9', revision_number: 3, published_at: '2026-08-19T09:00:00Z' },
  owners: [owner()],
  is_favorite: false,
  last_edited_by: owner(),
  last_edited_at: '2026-08-19T09:00:00Z',
  ...overrides,
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('mapWikiOwner', () => {
  it('snake_case owners[]를 camelCase 담당자로 옮긴다', () => {
    expect(mapWikiOwner(owner())).toEqual({
      userId: 7,
      displayName: '팀원F',
      profileImageUrl: 'https://cdn.example.com/7.png',
    });
  });

  it('사진 없는 담당자의 null을 그대로 보존한다', () => {
    expect(mapWikiOwner(owner({ profile_image_url: null })).profileImageUrl).toBeNull();
  });
});

describe('mapDocumentStatus', () => {
  it('published를 reviewed로 옮긴다', () => {
    expect(mapDocumentStatus('published')).toBe('reviewed');
  });

  it('pending_review는 이름이 같아 그대로 간다', () => {
    expect(mapDocumentStatus('pending_review')).toBe('pending_review');
  });

  it('no_revision은 대응 배지가 없어 열린 값으로 통과시킨다', () => {
    expect(mapDocumentStatus('no_revision')).toBe('no_revision');
  });
});

describe('mapWikiChannelListItem', () => {
  it('is_admin·document_count·folders를 함께 옮긴다', () => {
    expect(mapWikiChannelListItem(channel())).toEqual({
      id: 'ch-1',
      name: '결제',
      workspaceId: 3,
      isAdmin: true,
      documentCount: 12,
      folders: [
        {
          id: 'fd-1',
          name: '장애 대응',
          channelId: 'ch-1',
          createdAt: '2026-08-01T00:00:00Z',
          createdBy: { userId: 7, displayName: '팀원F', profileImageUrl: 'https://cdn.example.com/7.png' },
          lastActivityAt: '2026-08-19T09:00:00Z',
        },
      ],
    });
  });

  it('만든 사람이 없는 폴더는 null을 그대로 보존한다 — 컬럼 이전 폴더가 실재한다', () => {
    const folders = mapWikiChannelListItem(
      channel({
        folders: [
          {
            id: 'fd-legacy',
            name: '이전 폴더',
            channel_id: 'ch-1',
            created_at: '2026-01-01T00:00:00Z',
            created_by: null,
            last_activity_at: null,
          },
        ],
      }),
    ).folders;

    expect(folders[0]).toMatchObject({ createdBy: null, lastActivityAt: null });
  });
});

describe('resolveDocumentBreadcrumbs', () => {
  const index = createWikiLocationIndex([channel(), channel({ id: 'ch-2', name: '계정', folders: [] })]);

  it('채널·폴더 id를 이름 경로로 푼다', () => {
    expect(resolveDocumentBreadcrumbs(index, 'ch-1', 'fd-1')).toEqual([
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '장애 대응' },
    ]);
  });

  it('채널 루트 문서는 채널 마디만 만든다', () => {
    expect(resolveDocumentBreadcrumbs(index, 'ch-2', null)).toEqual([{ kind: 'channel', label: '계정' }]);
  });

  it('미분류 문서는 경로가 비어 있다', () => {
    expect(resolveDocumentBreadcrumbs(index, null, null)).toEqual([]);
  });

  it('색인에 없는 id는 마디를 만들지 않는다', () => {
    expect(resolveDocumentBreadcrumbs(index, 'ch-unknown', 'fd-unknown')).toEqual([]);
  });
});

describe('mapWikiArtifactRow', () => {
  it('최근 활동 시각은 서버 필드를 그대로 쓰고 표시 문자열만 만든다', () => {
    const row = mapWikiArtifactRow(artifact());

    expect(row.lastActivityAt).toBe('2026-08-19T09:00:00Z');
    expect(row.lastActivityLabel).toBe('3시간 전');
  });

  it('발행판이 없어도 서버가 준 활동 시각을 그대로 쓴다', () => {
    const row = mapWikiArtifactRow(
      artifact({ status: 'no_revision', latest_revision: null, last_activity_at: '2026-08-18T12:00:00Z' }),
    );

    expect(row.lastActivityAt).toBe('2026-08-18T12:00:00Z');
    expect(row.createdAt).toBe('2026-08-01T00:00:00Z');
  });

  it('담당자 없는 문서는 빈 배열로 온다', () => {
    expect(mapWikiArtifactRow(artifact({ owners: [] })).owners).toEqual([]);
  });

  it('최종 편집자를 담당자와 같은 모양으로 옮긴다', () => {
    const row = mapWikiArtifactRow(artifact());

    expect(row.lastEditedBy).toEqual({
      userId: 7,
      displayName: '팀원F',
      profileImageUrl: 'https://cdn.example.com/7.png',
    });
    expect(row.lastEditedAt).toBe('2026-08-19T09:00:00Z');
  });

  it('발행판이 없으면 최종 편집자와 시각이 둘 다 없다', () => {
    const row = mapWikiArtifactRow(artifact({ last_edited_by: null, last_edited_at: null }));

    expect([row.lastEditedBy, row.lastEditedAt]).toEqual([null, null]);
  });

  it('승인자가 사용자로 이어지지 않으면 사람만 빠지고 시각은 남는다', () => {
    const row = mapWikiArtifactRow(artifact({ last_edited_by: null }));

    expect(row.lastEditedBy).toBeNull();
    expect(row.lastEditedAt).toBe('2026-08-19T09:00:00Z');
  });

  it('경로는 밖에서 받은 것을 그대로 싣는다', () => {
    const breadcrumbs = [{ kind: 'channel', label: '결제' }] as const;

    expect(mapWikiArtifactRow(artifact(), breadcrumbs).breadcrumbs).toBe(breadcrumbs);
  });
});

describe('mapWikiArtifactRows', () => {
  it('색인을 주면 줄마다 경로를 채운다', () => {
    const rows = mapWikiArtifactRows([artifact()], createWikiLocationIndex([channel()]));

    expect(rows[0].breadcrumbs).toEqual([
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '장애 대응' },
    ]);
  });

  it('색인이 없으면 경로를 비운 채로 옮긴다', () => {
    expect(mapWikiArtifactRows([artifact()])[0].breadcrumbs).toEqual([]);
  });
});

describe('mapWikiMembers', () => {
  it('멤버 목록 봉투를 벗겨 담당자와 같은 모양으로 옮긴다', () => {
    expect(mapWikiMembers({ items: [owner(), owner({ user_id: 9, display_name: '이진수' })] })).toEqual([
      { userId: 7, displayName: '팀원F', profileImageUrl: 'https://cdn.example.com/7.png' },
      { userId: 9, displayName: '이진수', profileImageUrl: 'https://cdn.example.com/7.png' },
    ]);
  });

  it('구성원이 없으면 빈 배열이다', () => {
    expect(mapWikiMembers({ items: [] })).toEqual([]);
  });
});

describe('WikiArtifactListParams', () => {
  it('담당자 조건을 하나씩 쓰는 것은 통과하고, owner_user_id는 여러 명을 받는다', () => {
    const byOwner: WikiArtifactListParams = { owner_user_id: [7, 9], sort: 'created_at', order: 'asc', q: '결제' };
    const byUnassigned: WikiArtifactListParams = { unassigned: true };

    expect([byOwner.owner_user_id, byUnassigned.unassigned]).toEqual([[7, 9], true]);
  });

  it('owner_user_id에 낱개 숫자는 실리지 않는다 — 서버가 반복 파라미터를 읽는다', () => {
    // @ts-expect-error 담당자 조건은 배열이다
    const scalar: WikiArtifactListParams = { owner_user_id: 7 };

    expect(scalar).toBeDefined();
  });

  it('owner_user_id와 unassigned 동시 지정은 타입이 막는다(서버는 422)', () => {
    // @ts-expect-error 두 담당자 조건은 함께 실릴 수 없다
    const conflicting: WikiArtifactListParams = { owner_user_id: [7], unassigned: true };

    expect(conflicting).toBeDefined();
  });
});
