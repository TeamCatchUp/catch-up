import type { ReactElement } from 'react';
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import type { InquiryAutomationItem } from '../../types/automationApi';
import AgentStudioPage from './AgentStudioPage';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

function renderWithQueryClient(ui: ReactElement) {
  const queryClientRef: { current?: QueryClient } = {};
  const mutationCache = new MutationCache({
    onSuccess: (_data, _variables, _context, mutation) => {
      const invalidates = mutation.meta?.invalidates as string[][] | undefined;
      invalidates?.forEach((queryKey) => {
        queryClientRef.current?.invalidateQueries({ queryKey });
      });
    },
  });

  const queryClient = new QueryClient({
    mutationCache,
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  queryClientRef.current = queryClient;

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function useInquiryAutomationList(items: InquiryAutomationItem[]) {
  server.use(http.get('/api/v1/automations/inqueries', () => HttpResponse.json(items)));
}

const activeAutomation: InquiryAutomationItem = {
  agent_spec_id: 1,
  status: 'active',
  channel_talk_credential_id: 10,
  slack_channel_id: 'C111',
  slack_credential_id: 20,
  guide_instruction: null,
  quiet_period_seconds: 60,
  trigger_id: 30,
};

const inactiveAutomation: InquiryAutomationItem = {
  agent_spec_id: 2,
  status: 'inactive',
  channel_talk_credential_id: 11,
  slack_channel_id: 'C222',
  slack_credential_id: 21,
  guide_instruction: '짧게 작성',
  quiet_period_seconds: 60,
  trigger_id: 31,
};

beforeEach(() => {
  mockPush.mockClear();
});

describe('AgentStudioPage', () => {
  it('renders the Agent Studio list from automations API', async () => {
    useInquiryAutomationList([activeAutomation, inactiveAutomation]);

    renderWithQueryClient(<AgentStudioPage />);

    expect(screen.getByRole('heading', { name: '우리 팀의 Agent' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agent 만들기' })).toBeInTheDocument();
    expect(await screen.findAllByText('문의 대응 리포트 만들기')).toHaveLength(2);
    expect(screen.getByText('제작 중인 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
  });

  it('moves to the create route when Agent 만들기 is clicked', async () => {
    const user = userEvent.setup();
    useInquiryAutomationList([]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: 'Agent 만들기' }));

    expect(mockPush).toHaveBeenCalledWith('/agent-studio/new');
  });

  it('updates the selected filter chip locally', async () => {
    const user = userEvent.setup();
    useInquiryAutomationList([inactiveAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '사용 안함' }));

    expect(screen.getByRole('button', { name: '사용 안함' })).toHaveAttribute('data-selected', 'true');
    expect(screen.getByRole('button', { name: '사용 안함' })).toHaveAttribute('aria-pressed', 'true');
    expect(await screen.findByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('updates inactive automation to active when 다시 운영하기 is clicked', async () => {
    const user = userEvent.setup();
    const patchRequests: unknown[] = [];

    useInquiryAutomationList([inactiveAutomation]);
    server.use(
      http.patch('/api/v1/automations/inqueries/2', async ({ request }) => {
        patchRequests.push(await request.json());
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithQueryClient(<AgentStudioPage />);

    await user.click(await screen.findByRole('button', { name: '다시 운영하기' }));

    expect(patchRequests).toEqual([{ status: 'active' }]);
  });

  it('updates active automation to inactive when 사용 안함 is clicked', async () => {
    const user = userEvent.setup();
    const patchRequests: unknown[] = [];

    useInquiryAutomationList([activeAutomation]);
    server.use(
      http.patch('/api/v1/automations/inqueries/1', async ({ request }) => {
        patchRequests.push(await request.json());
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithQueryClient(<AgentStudioPage />);

    await user.click(await screen.findByRole('button', { name: '문의 대응 리포트 만들기 사용 안함' }));

    expect(patchRequests).toEqual([{ status: 'inactive' }]);
  });
});
