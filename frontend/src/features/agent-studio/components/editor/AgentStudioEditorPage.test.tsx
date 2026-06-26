import type { ReactElement } from 'react';
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import type { AutomationCredentialItem, AutomationTargetItem } from '../../types/automationApi';
import AgentStudioEditorPage from './AgentStudioEditorPage';

const mockBack = vi.fn();
const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ back: mockBack, push: mockPush }),
}));

if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = vi.fn();
}

if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = vi.fn();
}

if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = vi.fn();
}

const slackCredential: AutomationCredentialItem = {
  connector: 'slack',
  credential_id: 20,
  display_name: 'Catch Up',
  external_id: 'T0123',
  external_name: 'Catch Up',
  is_configured: true,
  metadata: {},
};

const channelTalkTarget: AutomationTargetItem = {
  connector: 'channel_talk',
  credential_id: 10,
  target_id: 'channel-talk-main',
  display_name: '채널톡 기본 채널',
  target_type: 'channel',
  is_accessible: true,
  metadata: {},
};

const slackTarget: AutomationTargetItem = {
  connector: 'slack',
  credential_id: 20,
  target_id: 'C123',
  display_name: 'cs-response',
  target_type: 'channel',
  is_accessible: true,
  metadata: {},
};

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

function mockEditorSuccessHandlers() {
  server.use(
    http.get('/api/v1/automations/credentials', ({ request }) => {
      const url = new URL(request.url);

      if (url.searchParams.get('connector') !== 'slack') {
        return new HttpResponse(null, { status: 500 });
      }

      return HttpResponse.json({
        connector: 'slack',
        total_credentials: 1,
        credentials: [slackCredential],
      });
    }),
    http.get('/api/v1/automations/targets', ({ request }) => {
      const url = new URL(request.url);
      const connector = url.searchParams.get('connector');
      const credentialId = url.searchParams.get('credential_id');

      if (connector === 'channel_talk' && credentialId === null) {
        return HttpResponse.json({
          connector: 'channel_talk',
          credential_id: null,
          total_targets: 1,
          targets: [channelTalkTarget],
        });
      }

      if (connector === 'slack' && credentialId === '20') {
        return HttpResponse.json({
          connector: 'slack',
          credential_id: 20,
          total_targets: 1,
          targets: [slackTarget],
        });
      }

      return new HttpResponse(null, { status: 500 });
    }),
    http.get('/api/v1/version', () => HttpResponse.json('1.2.3')),
  );
}

function renderEditor() {
  mockEditorSuccessHandlers();
  return renderWithQueryClient(<AgentStudioEditorPage />);
}

async function selectRequiredAutomationFields(user: ReturnType<typeof userEvent.setup>) {
  const channelTalkSelect = await screen.findByRole('combobox', { name: /어떤 채널로 들어오는 문의/ });

  await waitFor(() => expect(channelTalkSelect).not.toBeDisabled());
  await user.click(channelTalkSelect);
  await user.click(await screen.findByRole('option', { name: '채널톡 기본 채널' }));

  await waitFor(() =>
    expect(screen.getByRole('combobox', { name: /누구의 권한을 가지고 조회/ })).toHaveTextContent('Catch Up'),
  );

  const slackChannelSelect = screen.getByRole('combobox', { name: /Slack 채널을 선택/ });

  await waitFor(() => expect(slackChannelSelect).not.toBeDisabled());
  await user.click(slackChannelSelect);
  await user.click(await screen.findByRole('option', { name: 'cs-response' }));

  return { channelTalkSelect, slackChannelSelect };
}

beforeEach(() => {
  mockBack.mockClear();
  mockPush.mockClear();
});

describe('AgentStudioEditorPage', () => {
  it('renders the editor setting sections from fixtures', () => {
    renderEditor();

    expect(screen.getByRole('heading', { name: '설정' })).toBeInTheDocument();
    expect(screen.getByText('채널톡 문의 유입 감지')).toBeInTheDocument();
    expect(screen.getByText('Slack으로 메시지 보내기')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '문의 대응 리포트 만들기' })).toBeInTheDocument();
  });

  it('keeps deploy disabled before an instruction is entered', () => {
    renderEditor();

    expect(screen.getByRole('button', { name: '배포하기' })).toBeDisabled();
  });

  it('moves back when the back button is clicked', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole('button', { name: 'Agent Studio로 돌아가기' }));

    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  it('renders the Agent Studio breadcrumb button as a link to the list page', () => {
    renderEditor();

    expect(screen.getByRole('link', { name: 'Agent Studio' })).toHaveAttribute('href', '/agent-studio');
  });

  it('keeps the settings header sticky while the right pane scrolls', () => {
    renderEditor();

    const settingsHeader = screen.getByRole('button', { name: 'Agent Studio로 돌아가기' }).closest('header');

    expect(settingsHeader).toHaveClass('sticky', 'top-0', 'z-10', 'bg-fill-normal-assistive-dark');
  });

  it('opens the same more menu as the home header from the settings header', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole('button', { name: '설정 더보기' }));

    expect(await screen.findByRole('menuitem', { name: '도움말' })).toBeInTheDocument();
    expect(screen.getByText('버전 기록')).toBeInTheDocument();
    expect(await screen.findByText('v1.2.3')).toBeInTheDocument();
  });

  it('updates the instruction count while typing', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.type(screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?'), '응답은 간결하게 작성');

    expect(screen.getByText('11/500')).toBeInTheDocument();
  });

  it('keeps the instruction field spacing stable before and after typing', async () => {
    const user = userEvent.setup();
    renderEditor();

    const instructionField = screen.getByRole('textbox');
    const instructionContainer = instructionField.parentElement;

    expect(instructionContainer).toHaveClass('gap-4');

    await user.type(instructionField, 'a');

    expect(instructionContainer).toHaveClass('gap-4');
    expect(instructionContainer).not.toHaveClass('gap-2.5');
  });

  it('marks the instruction field as invalid at the max length', () => {
    renderEditor();

    const instructionField = screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?');

    fireEvent.change(instructionField, { target: { value: '가'.repeat(500) } });

    expect(instructionField).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('500/500')).toHaveClass('text-status-destructive');
  });

  it('renders unselected channel fields as select placeholders', () => {
    renderEditor();

    expect(screen.getByRole('combobox', { name: /어떤 채널로 들어오는 문의/ })).toHaveAttribute('data-placeholder');
    expect(screen.getByRole('combobox', { name: /Slack 채널을 선택/ })).toHaveAttribute('data-placeholder');
    expect(screen.getByText('채널톡 내 채널을 선택해주세요')).toBeInTheDocument();
    expect(screen.getByText('Slack 내 채널을 선택해주세요')).toBeInTheDocument();
  });

  it('loads selectable channel and Slack fields from automation APIs', async () => {
    const user = userEvent.setup();
    renderEditor();

    const { channelTalkSelect, slackChannelSelect } = await selectRequiredAutomationFields(user);

    expect(channelTalkSelect).toHaveTextContent('채널톡 기본 채널');
    expect(slackChannelSelect).toHaveTextContent('cs-response');
  });

  it('shows the available quiet period options', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole('combobox', { name: /몇 분 후에 Agent를 실행할까요/ }));

    expect(await screen.findByRole('option', { name: '1분' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '3분' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '5분' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '10분' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '30분' })).toBeInTheDocument();
  });

  it('enables deploy after an instruction is entered', async () => {
    const user = userEvent.setup();
    renderEditor();

    const publishButton = screen.getByRole('button', { name: '배포하기' });

    expect(publishButton).toBeDisabled();

    await user.type(screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?'), '가');

    await waitFor(() => expect(publishButton).not.toBeDisabled());
  });

  it('publishes the selected automation settings and moves to the list after success', async () => {
    const user = userEvent.setup();
    const publishRequests: unknown[] = [];
    let resolvePublish!: () => void;
    const publishSettled = new Promise<void>((resolve) => {
      resolvePublish = resolve;
    });

    server.use(
      http.post('/api/v1/automations/inquiries/publish', async ({ request }) => {
        publishRequests.push(await request.json());
        await publishSettled;

        return HttpResponse.json({
          agent_spec_id: 1,
          trigger_id: 2,
          status: 'active',
          channel_talk_channel_id: 'channel-talk-main',
          channel_talk_channel_name: '채널톡 기본 채널',
          quiet_period_seconds: 60,
          slack_channel_id: 'C123',
          start_event_type: 'message_created',
          reset_event_types: ['message_created'],
        });
      }),
    );
    renderEditor();

    await selectRequiredAutomationFields(user);
    await user.click(screen.getByRole('combobox', { name: /몇 분 후에 Agent를 실행할까요/ }));
    await user.click(await screen.findByRole('option', { name: '30분' }));
    await user.type(screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?'), '프로젝트 맥락 반영');

    const publishButton = screen.getByRole('button', { name: '배포하기' });

    await waitFor(() => expect(publishButton).not.toBeDisabled());
    await user.click(publishButton);

    await waitFor(() => expect(publishRequests).toHaveLength(1));
    expect(publishButton).toBeDisabled();
    expect(publishButton).toHaveTextContent('배포하기');
    expect(publishRequests).toEqual([
      {
        channel_talk_credential_id: 10,
        quiet_period_seconds: 1800,
        slack_channel: {
          credential_id: 20,
          channel_id: 'C123',
          channel_name: 'cs-response',
        },
        guide_instruction: '프로젝트 맥락 반영',
      },
    ]);

    resolvePublish();

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/agent-studio'));
  });

  it('prevents duplicate publish requests while a publish is already in flight', async () => {
    const user = userEvent.setup();
    const publishRequests: unknown[] = [];
    let resolvePublish!: () => void;
    const publishSettled = new Promise<void>((resolve) => {
      resolvePublish = resolve;
    });

    server.use(
      http.post('/api/v1/automations/inquiries/publish', async ({ request }) => {
        publishRequests.push(await request.json());
        await publishSettled;

        return HttpResponse.json({
          agent_spec_id: 1,
          trigger_id: 2,
          status: 'active',
          channel_talk_channel_id: 'channel-talk-main',
          channel_talk_channel_name: '채널톡 기본 채널',
          quiet_period_seconds: 60,
          slack_channel_id: 'C123',
          start_event_type: 'message_created',
          reset_event_types: ['message_created'],
        });
      }),
    );

    renderEditor();

    await selectRequiredAutomationFields(user);
    await user.click(screen.getByRole('combobox', { name: /몇 분 후에 Agent를 실행할까요/ }));
    await user.click(await screen.findByRole('option', { name: '30분' }));
    await user.type(screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?'), '프로젝트 맥락 반영');

    const publishButton = screen.getByRole('button', { name: '배포하기' });

    await waitFor(() => expect(publishButton).not.toBeDisabled());

    publishButton.click();
    publishButton.click();

    await waitFor(() => expect(publishRequests).toHaveLength(1));

    resolvePublish();
  });
});
