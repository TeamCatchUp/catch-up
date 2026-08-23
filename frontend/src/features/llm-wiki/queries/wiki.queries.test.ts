import { hashKey, QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  WikiArtifactDocumentDto,
  WikiArtifactListDto,
  WikiArtifactListParams,
  WikiChannelListDto,
  WikiDefinitionPresetsDto,
  WikiFavoriteListDto,
  WikiWorkspaceMemberListDto,
} from '../api/wikiDto';
import {
  fetchWikiArtifactDocument,
  fetchWikiArtifacts,
  fetchWikiChannels,
  fetchWikiDefinitionPresets,
  fetchWikiFavorites,
  fetchWikiMembers,
} from '../api/wikiRequests';
import { wikiQueries } from './wiki.queries';

// 실 요청을 막고 queryFn이 fetcher에 넘기는 인자만 본다
vi.mock('../api/wikiRequests', () => ({
  fetchWikiArtifactDocument: vi.fn(),
  fetchWikiArtifacts: vi.fn(),
  fetchWikiChannels: vi.fn(),
  fetchWikiDefinitionPresets: vi.fn(),
  fetchWikiFavorites: vi.fn(),
  fetchWikiMembers: vi.fn(),
}));

const CHANNEL_LIST: WikiChannelListDto = { channels: [] };
const PRESETS: WikiDefinitionPresetsDto = { domains: [], styles: [] };
const MEMBERS: WikiWorkspaceMemberListDto = { items: [] };
const ARTIFACT_LIST: WikiArtifactListDto = { items: [], total: 0, limit: 50, offset: 0 };
const FAVORITES: WikiFavoriteListDto = { items: [] };
const DOCUMENT: WikiArtifactDocumentDto = {
  artifact_id: 'af-1',
  channel_id: 'ch-1',
  definition_id: 'def-1',
  kind: 'incident_guide',
  title: '결제 실패 대응 가이드',
  folder_id: 'fd-1',
  owners: [],
  is_favorite: false,
  revision_id: 'rv-9',
  published_at: '2026-08-19T09:00:00Z',
  last_edited_by: null,
  last_edited_at: null,
  blocks: [],
};

/** 캐시가 빈 클라이언트. staleTime 때문에 두 번째 호출이 fetcher를 건너뛰는 것을 막는다 */
const freshClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

const ENTRIES: ReadonlyArray<readonly [string, readonly unknown[]]> = [
  ['channels', wikiQueries.channels().queryKey],
  ['definitionPresets', wikiQueries.definitionPresets().queryKey],
  ['members', wikiQueries.members().queryKey],
  ['artifacts', wikiQueries.artifacts().queryKey],
  ['artifact', wikiQueries.artifact('af-1').queryKey],
  ['favorites', wikiQueries.favorites().queryKey],
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchWikiChannels).mockResolvedValue(CHANNEL_LIST);
  vi.mocked(fetchWikiDefinitionPresets).mockResolvedValue(PRESETS);
  vi.mocked(fetchWikiMembers).mockResolvedValue(MEMBERS);
  vi.mocked(fetchWikiArtifacts).mockResolvedValue(ARTIFACT_LIST);
  vi.mocked(fetchWikiArtifactDocument).mockResolvedValue(DOCUMENT);
  vi.mocked(fetchWikiFavorites).mockResolvedValue(FAVORITES);
});

describe('wikiQueries 키 뿌리', () => {
  it('뿌리는 ["llm-wiki", "wiki"]다', () => {
    expect(wikiQueries.all()).toEqual(['llm-wiki', 'wiki']);
  });

  it('모든 엔트리가 그 뿌리 아래로 들어간다 — 뮤테이션이 한 번에 무효화하는 계약이다', () => {
    for (const [name, key] of ENTRIES) {
      expect([name, key.slice(0, 2)]).toEqual([name, ['llm-wiki', 'wiki']]);
    }
  });

  it('엔트리끼리 키가 겹치지 않는다 — 한 캐시 자리를 두 화면이 나눠 쓰지 않는다', () => {
    expect(new Set(ENTRIES.map(([, key]) => hashKey(key))).size).toBe(ENTRIES.length);
  });
});

describe('wikiQueries.artifacts 키', () => {
  it('같은 파라미터는 같은 캐시 자리를 가리킨다 — 객체 identity가 아니라 값으로 잡힌다', () => {
    const first = wikiQueries.artifacts({ channel_id: 'ch-1', limit: 20 }).queryKey;
    const second = wikiQueries.artifacts({ channel_id: 'ch-1', limit: 20 }).queryKey;

    expect(first).toEqual(second);
    expect(hashKey(first)).toBe(hashKey(second));
  });

  it('프로퍼티 순서가 달라도 같은 자리다 — 해시가 키를 정렬해 직렬화한다', () => {
    const declared = wikiQueries.artifacts({ channel_id: 'ch-1', limit: 20, offset: 40 }).queryKey;
    const shuffled = wikiQueries.artifacts({ offset: 40, limit: 20, channel_id: 'ch-1' }).queryKey;

    expect(hashKey(declared)).toBe(hashKey(shuffled));
  });

  it('필터가 다르면 다른 자리다', () => {
    const base = wikiQueries.artifacts({ channel_id: 'ch-1' }).queryKey;

    expect(hashKey(base)).not.toBe(hashKey(wikiQueries.artifacts({ channel_id: 'ch-2' }).queryKey));
    expect(hashKey(base)).not.toBe(hashKey(wikiQueries.artifacts({ channel_id: 'ch-1', status: 'published' }).queryKey));
    expect(hashKey(base)).not.toBe(hashKey(wikiQueries.artifacts({ channel_id: 'ch-1', q: '결제' }).queryKey));
  });

  it('페이지가 다르면 다른 자리다 — 다음 쪽이 앞 쪽 위에 덮어쓰지 않는다', () => {
    const first = wikiQueries.artifacts({ limit: 50, offset: 0 }).queryKey;
    const second = wikiQueries.artifacts({ limit: 50, offset: 50 }).queryKey;

    expect(hashKey(first)).not.toBe(hashKey(second));
    expect(hashKey(first)).not.toBe(hashKey(wikiQueries.artifacts({ limit: 20, offset: 0 }).queryKey));
  });

  it('정렬이 다르면 다른 자리다', () => {
    const base = wikiQueries.artifacts({ sort: 'last_activity', order: 'desc' }).queryKey;

    expect(hashKey(base)).not.toBe(hashKey(wikiQueries.artifacts({ sort: 'created_at', order: 'desc' }).queryKey));
    expect(hashKey(base)).not.toBe(hashKey(wikiQueries.artifacts({ sort: 'last_activity', order: 'asc' }).queryKey));
  });

  it('파라미터를 생략하면 빈 객체가 실린다 — 필터 없는 목록도 자기 자리를 갖는다', () => {
    expect(wikiQueries.artifacts().queryKey).toEqual(['llm-wiki', 'wiki', 'artifacts', {}]);
  });

  it('담당자 조건은 서로 다른 자리다 — 미지정 필터가 특정 담당자 결과를 덮지 않는다', () => {
    const byOwner = wikiQueries.artifacts({ owner_user_id: [7] }).queryKey;
    const unassigned = wikiQueries.artifacts({ unassigned: true }).queryKey;

    expect(hashKey(byOwner)).not.toBe(hashKey(unassigned));
  });

  it('고른 담당자가 다르면 다른 자리다 — 다중 선택이 한 명 결과 위에 덮어쓰지 않는다', () => {
    const one = wikiQueries.artifacts({ owner_user_id: [7] }).queryKey;
    const two = wikiQueries.artifacts({ owner_user_id: [7, 9] }).queryKey;

    expect(hashKey(one)).not.toBe(hashKey(two));
  });
});

describe('wikiQueries.artifact 키와 enabled', () => {
  it('문서가 다르면 다른 자리다', () => {
    expect(hashKey(wikiQueries.artifact('af-1').queryKey)).not.toBe(hashKey(wikiQueries.artifact('af-2').queryKey));
  });

  it('artifactId가 비면 조회하지 않는다 — 라우트 파라미터가 오기 전에 빈 경로로 요청이 나가지 않는다', () => {
    expect(wikiQueries.artifact('').enabled).toBe(false);
  });

  it('artifactId가 있으면 조회한다', () => {
    expect(wikiQueries.artifact('af-1').enabled).toBe(true);
  });

  it('나머지 엔트리에는 잠금 조건이 없다 — 파라미터 없이도 항상 연다', () => {
    expect(wikiQueries.channels().enabled).toBeUndefined();
    expect(wikiQueries.definitionPresets().enabled).toBeUndefined();
    expect(wikiQueries.members().enabled).toBeUndefined();
    expect(wikiQueries.artifacts().enabled).toBeUndefined();
    expect(wikiQueries.favorites().enabled).toBeUndefined();
  });
});

describe('wikiQueries 신선도', () => {
  it('preset 카탈로그는 만료되지 않고, 이름 공급원은 문서 목록보다 오래 신선하다', () => {
    const artifacts = wikiQueries.artifacts().staleTime as number;

    expect(wikiQueries.definitionPresets().staleTime).toBe(Infinity);
    expect(wikiQueries.channels().staleTime as number).toBeGreaterThan(artifacts);
    expect(wikiQueries.members().staleTime as number).toBeGreaterThan(artifacts);
  });
});

describe('wikiQueries queryFn', () => {
  it('문서 목록은 필터·정렬·페이지를 그대로 fetcher에 넘긴다', async () => {
    const params: WikiArtifactListParams = {
      channel_id: 'ch-1',
      folder_id: 'fd-1',
      kind: 'incident_guide',
      status: 'published',
      q: '결제',
      sort: 'created_at',
      order: 'asc',
      limit: 20,
      offset: 40,
    };

    await freshClient().fetchQuery(wikiQueries.artifacts(params));

    expect(fetchWikiArtifacts).toHaveBeenCalledWith(params, expect.any(AbortSignal));
  });

  it('파라미터 없는 목록은 빈 객체를 넘긴다', async () => {
    await freshClient().fetchQuery(wikiQueries.artifacts());

    expect(fetchWikiArtifacts).toHaveBeenCalledWith({}, expect.any(AbortSignal));
  });

  it('발행판 상세는 artifactId를 경로 인자로 넘긴다', async () => {
    await freshClient().fetchQuery(wikiQueries.artifact('af-1'));

    expect(fetchWikiArtifactDocument).toHaveBeenCalledWith('af-1', expect.any(AbortSignal));
  });

  it('파라미터 없는 엔트리는 signal만 넘긴다 — 취소가 fetcher까지 이어진다', async () => {
    const client = freshClient();

    await client.fetchQuery(wikiQueries.channels());
    await client.fetchQuery(wikiQueries.definitionPresets());
    await client.fetchQuery(wikiQueries.members());
    await client.fetchQuery(wikiQueries.favorites());

    expect(fetchWikiChannels).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(fetchWikiDefinitionPresets).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(fetchWikiMembers).toHaveBeenCalledWith(expect.any(AbortSignal));
    expect(fetchWikiFavorites).toHaveBeenCalledWith(expect.any(AbortSignal));
  });
});
