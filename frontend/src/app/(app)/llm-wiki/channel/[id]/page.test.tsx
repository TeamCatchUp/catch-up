import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import Page from './page';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: 'ch-1' }),
  notFound: () => {
    throw new Error('notFound');
  },
}));

vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const FOLDER_COUNT = 25;

const channelResponse = () => ({
  channels: [
    {
      id: 'ch-1',
      name: '결제',
      workspace_id: 1,
      is_admin: true,
      document_count: 0,
      folders: Array.from({ length: FOLDER_COUNT }, (_, index) => ({
        id: `fd-${index + 1}`,
        name: `폴더 ${index + 1}`,
        channel_id: 'ch-1',
      })),
      purpose_presets: [],
      definitions: [],
    },
  ],
});

beforeEach(() => {
  server.use(http.get('*/api/v1/wiki/channels', () => HttpResponse.json(channelResponse())));
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

describe('채널 화면 쪽 크기 배선', () => {
  it('기본 20개씩 잘라 내고 나머지는 다음 쪽으로 넘긴다', async () => {
    renderPage();

    expect(await screen.findByText('폴더 1')).toBeInTheDocument();
    expect(screen.getByText('폴더 20')).toBeInTheDocument();
    expect(screen.queryByText('폴더 21')).toBeNull();
  });

  it('쪽 크기를 바꾸면 1쪽으로 돌아가고 그 크기만큼만 남는다', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole('button', { name: '2' }));
    expect(screen.getByText('폴더 21')).toBeInTheDocument();

    await selectPageSize(user, '20', '10');

    // 2쪽에 머무르면 11~20을 그린다 — 1쪽으로 돌아왔는지가 이 단언의 핵심이다
    expect(await screen.findByText('폴더 1')).toBeInTheDocument();
    expect(screen.getByText('폴더 10')).toBeInTheDocument();
    expect(screen.queryByText('폴더 11')).toBeNull();
    expect(screen.queryByText('폴더 21')).toBeNull();
  });
});
