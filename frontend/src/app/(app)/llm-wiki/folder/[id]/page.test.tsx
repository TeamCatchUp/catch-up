import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import Page from './page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: 'fd-1' }),
  notFound: () => {
    throw new Error('notFound');
  },
}));

vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const TOTAL_DOCUMENTS = 60;

const channelResponse = (isAdmin = true) => ({
  channels: [
    {
      id: 'ch-1',
      name: '결제',
      workspace_id: 1,
      is_admin: isAdmin,
      document_count: TOTAL_DOCUMENTS,
      folders: [
        {
          id: 'fd-1',
          name: '승인·실패 처리',
          channel_id: 'ch-1',
          created_at: '2026-08-19T00:00:00Z',
          created_by: { user_id: 7, display_name: '팀원F', profile_image_url: null },
          last_activity_at: '2026-08-19T00:00:00Z',
        },
      ],
      purpose_presets: [],
      definitions: [],
    },
  ],
});

const artifactResponse = (limit: number, offset: number) => ({
  items: [
    {
      artifact_id: `art-${offset}`,
      kind: 'faq',
      title: `문서 ${offset + 1}`,
      channel_id: 'ch-1',
      folder_id: 'fd-1',
      created_at: '2026-08-19T00:00:00Z',
      last_activity_at: '2026-08-19T00:00:00Z',
      status: 'published',
      pending_proposal_count: 0,
      latest_revision: null,
      owners: [],
      is_favorite: false,
      last_edited_by: { user_id: 7, display_name: '팀원F', profile_image_url: null },
      last_edited_at: '2026-08-19T00:00:00Z',
    },
  ],
  total: TOTAL_DOCUMENTS,
  limit,
  offset,
});

/** 문서 목록에 실제로 나간 limit·offset 조합 */
let ranges: { limit: string | null; offset: string | null }[] = [];

beforeEach(() => {
  ranges = [];
  server.use(
    http.get('*/api/v1/wiki/channels', () => HttpResponse.json(channelResponse())),
    http.get('*/api/v1/wiki/artifacts', ({ request }) => {
      const params = new URL(request.url).searchParams;
      const limit = params.get('limit');
      const offset = params.get('offset');
      ranges.push({ limit, offset });
      return HttpResponse.json(artifactResponse(Number(limit ?? 20), Number(offset ?? 0)));
    }),
  );
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Page />
    </QueryClientProvider>,
  );
}

/** 푸터의 쪽 크기 드롭다운을 열고 원하는 값을 고른다 */
async function selectPageSize(user: ReturnType<typeof userEvent.setup>, current: string, next: string) {
  await user.click(screen.getByRole('button', { name: current }));
  await user.click(await screen.findByRole('menuitem', { name: next }));
}

describe('헤더 액션 배선', () => {
  it('관리자면 케밥이 서고 이름 바꾸기가 폴더 PATCH로 나간다', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.patch('*/api/v1/wiki/channels/ch-1/folders/fd-1', async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: '작업 더보기' }));
    await user.click(await screen.findByRole('button', { name: '이름 바꾸기' }));

    const field = await screen.findByRole('textbox', { name: '이름 바꾸기' });
    expect(field).toHaveValue('승인·실패 처리');
    await user.clear(field);
    await user.type(field, '승인 처리{Enter}');

    await waitFor(() => expect(bodies).toEqual([{ name: '승인 처리' }]));
  });

  it('관리자가 아니면 링크 복사만 남고 케밥이 서지 않는다', async () => {
    server.use(http.get('*/api/v1/wiki/channels', () => HttpResponse.json(channelResponse(false))));
    renderPage();

    expect(await screen.findByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '작업 더보기' })).toBeNull();
  });
});

describe('폴더 화면 쪽 크기 배선', () => {
  it('기본 20으로 첫 쪽을 부르고 쪽을 넘기면 offset이 따라간다', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(ranges).toContainEqual({ limit: '20', offset: '0' }));

    await user.click(await screen.findByRole('button', { name: '2' }));
    await waitFor(() => expect(ranges).toContainEqual({ limit: '20', offset: '20' }));
  });

  it('쪽 크기를 바꾸면 그 크기로는 첫 쪽만 부른다', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: '3' }));
    await waitFor(() => expect(ranges).toContainEqual({ limit: '20', offset: '40' }));

    await selectPageSize(user, '20', '50');

    // 바뀐 크기가 실린 요청은 전부 첫 쪽이어야 한다 — 이전 쪽 번호가 남으면 빈 쪽을 부른다
    await waitFor(() => expect(ranges.some((range) => range.limit === '50')).toBe(true));
    expect(ranges.filter((range) => range.limit === '50').every((range) => range.offset === '0')).toBe(true);
  });
});
