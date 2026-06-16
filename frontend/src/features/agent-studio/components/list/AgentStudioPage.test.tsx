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

function mockVersion() {
  server.use(http.get('/api/v1/version', () => HttpResponse.json('1.0.0')));
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

const secondActiveAutomation: InquiryAutomationItem = {
  agent_spec_id: 3,
  status: 'active',
  channel_talk_credential_id: 12,
  slack_channel_id: 'C333',
  slack_credential_id: 22,
  guide_instruction: '상세하게 작성',
  quiet_period_seconds: 300,
  trigger_id: 32,
};

const thirdActiveAutomation: InquiryAutomationItem = {
  agent_spec_id: 4,
  status: 'active',
  channel_talk_credential_id: 13,
  slack_channel_id: 'C444',
  slack_credential_id: 23,
  guide_instruction: '짧고 명확하게 작성',
  quiet_period_seconds: 600,
  trigger_id: 33,
};

const draftAutomation: InquiryAutomationItem = {
  agent_spec_id: 5,
  status: 'draft',
  channel_talk_credential_id: 14,
  slack_channel_id: 'C555',
  slack_credential_id: 24,
  guide_instruction: '초안을 먼저 제안',
  quiet_period_seconds: 180,
  trigger_id: 34,
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
    mockVersion();
    useInquiryAutomationList([activeAutomation, inactiveAutomation]);

    renderWithQueryClient(<AgentStudioPage />);

    expect(screen.getByRole('heading', { name: '우리 팀의 Agent' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agent 만들기' })).toBeInTheDocument();
    expect(await screen.findAllByText('문의 대응 리포트 만들기')).toHaveLength(2);
    expect(screen.getByText('제작 중인 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
  });

  it('keeps the active column visible with an empty placeholder when there is no active automation', async () => {
    mockVersion();
    useInquiryAutomationList([inactiveAutomation]);

    renderWithQueryClient(<AgentStudioPage />);

    expect(await screen.findByText('운영 중인 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.queryByText('아직 비활성 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
  });

  it('moves to the create route when Agent 만들기 is clicked', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: 'Agent 만들기' }));

    expect(mockPush).toHaveBeenCalledWith('/agent-studio/new');
  });

  it('updates the selected filter chip locally', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([inactiveAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '사용 안함' }));

    expect(screen.getByRole('button', { name: '사용 안함' })).toHaveAttribute('data-selected', 'true');
    expect(screen.getByRole('button', { name: '사용 안함' })).toHaveAttribute('aria-pressed', 'true');
    expect(await screen.findByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('shows the active empty placeholder when the active tab is selected without active automations', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([inactiveAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '운영중' }));

    expect(await screen.findByText('운영 중인 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '다시 운영하기' })).not.toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('shows only active cards when the active tab is selected', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([activeAutomation, secondActiveAutomation, thirdActiveAutomation, inactiveAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '운영중' }));

    expect(await screen.findAllByRole('button', { name: '사용하기' })).toHaveLength(3);
    expect(screen.getAllByText('운영중')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '다시 운영하기' })).not.toBeInTheDocument();
    expect(screen.queryByText('운영 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('아직 비활성 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('shows the draft empty placeholder when the draft tab is selected without draft automations', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([activeAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '제작중' }));

    expect(await screen.findByText('제작 중인 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.queryByText('운영 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '문의 대응 리포트 만들기 사용 안함' })).not.toBeInTheDocument();
  });

  it('shows only draft cards when the draft tab has draft automations', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([activeAutomation, draftAutomation, inactiveAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '제작중' }));

    expect(await screen.findAllByRole('button', { name: '사용하기' })).toHaveLength(1);
    expect(screen.getAllByText('제작중')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '다시 운영하기' })).not.toBeInTheDocument();
    expect(screen.queryByText('운영 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('아직 비활성 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('shows the inactive empty placeholder when the inactive tab is selected without inactive automations', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([activeAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '사용 안함' }));

    expect(await screen.findByText('아직 비활성 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.queryByText('운영 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('shows only inactive cards when the inactive tab has inactive automations', async () => {
    const user = userEvent.setup();
    mockVersion();
    useInquiryAutomationList([activeAutomation, inactiveAutomation]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '사용 안함' }));

    expect(await screen.findByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '사용하기' })).not.toBeInTheDocument();
    expect(screen.queryByText('운영 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.queryByText('아직 비활성 Agent가 없습니다.')).not.toBeInTheDocument();
  });

  it('renders multiple active cards without the active empty placeholder', async () => {
    mockVersion();
    useInquiryAutomationList([activeAutomation, secondActiveAutomation]);

    renderWithQueryClient(<AgentStudioPage />);

    expect(await screen.findAllByText('문의 대응 리포트 만들기')).toHaveLength(2);
    expect(screen.queryByText('운영 중인 Agent가 없습니다.')).not.toBeInTheDocument();
    expect(screen.getByText('아직 비활성 Agent가 없습니다.')).toBeInTheDocument();
  });

  it('updates inactive automation to active when 다시 운영하기 is clicked', async () => {
    const user = userEvent.setup();
    const patchRequests: unknown[] = [];

    mockVersion();
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

    mockVersion();
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

  it('opens the same more menu content used on the home header', async () => {
    const user = userEvent.setup();

    mockVersion();
    useInquiryAutomationList([]);
    renderWithQueryClient(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '더보기 메뉴' }));

    expect(await screen.findByRole('menuitem', { name: '도움말' })).toBeInTheDocument();
    expect(screen.getByText('버전 기록')).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
  });
});
