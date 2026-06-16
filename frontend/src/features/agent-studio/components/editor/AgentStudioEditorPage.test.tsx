import type { ReactElement } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function useEditorSuccessHandlers() {
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
  );
}

function renderEditor() {
  useEditorSuccessHandlers();
  return renderWithQueryClient(<AgentStudioEditorPage />);
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

  it('keeps deploy disabled until required fields are selected', () => {
    renderEditor();

    expect(screen.getByRole('button', { name: '배포하기' })).toBeDisabled();
  });

  it('moves back when the back button is clicked', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole('button', { name: 'Agent Studio로 돌아가기' }));

    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  it('updates the instruction count while typing', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.type(screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?'), '응답은 간결하게 작성');

    expect(screen.getByText('11/500')).toBeInTheDocument();
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

    const channelTalkSelect = await screen.findByRole('combobox', { name: /어떤 채널로 들어오는 문의/ });

    await waitFor(() => expect(channelTalkSelect).not.toBeDisabled());
    await user.click(channelTalkSelect);
    await user.click(await screen.findByRole('option', { name: '채널톡 기본 채널' }));

    expect(channelTalkSelect).toHaveTextContent('채널톡 기본 채널');

    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: /누구의 권한을 가지고 조회/ })).toHaveTextContent('Catch Up'),
    );

    const slackChannelSelect = screen.getByRole('combobox', { name: /Slack 채널을 선택/ });

    await waitFor(() => expect(slackChannelSelect).not.toBeDisabled());
    await user.click(slackChannelSelect);
    await user.click(await screen.findByRole('option', { name: 'cs-response' }));

    expect(slackChannelSelect).toHaveTextContent('cs-response');
  });
});
