import type { ReactElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { toast } from '@/shared/components/ui/toast';
import type { AutomationCredentialItem } from '@/shared/types/automationApi';
import { server } from '@/test/msw/server';

import {
  CHANNEL_PICKER_PLACEHOLDER,
  ONBOARDING_FINISH_LABEL,
  ONBOARDING_NEXT_LABEL,
  WIKI_NAME_FIELD,
} from '../../fixtures/llmWikiOnboardingFixtures';
import type { OnboardingStepNumber } from '../../utils/onboarding/resolveOnboardingStep';
import WikiOnboardingPage from './WikiOnboardingPage';

const mockPush = vi.fn();
const mockBack = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, back: mockBack, replace: vi.fn() }),
}));

vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = vi.fn();
}
if (!HTMLElement.prototype.releasePointerCapture) {
  HTMLElement.prototype.releasePointerCapture = vi.fn();
}
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = vi.fn();
}

const credential = (credentialId: number, displayName: string): AutomationCredentialItem => ({
  connector: 'channel_talk',
  credential_id: credentialId,
  display_name: displayName,
  external_id: `ct-${credentialId}`,
  external_name: displayName,
  is_configured: true,
  metadata: {},
});

const CREDENTIALS = [credential(11, '고객지원'), credential(12, '기술문의')];

interface RecordedRequest {
  url: string;
  body: unknown;
}

function renderOnboarding() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const withClient = (ui: ReactElement) => <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>;
  const view = render(withClient(<WikiOnboardingPage step={1} />));

  return {
    ...view,
    // 실제 라우팅은 URL의 step만 바꾼다 — 입력 상태는 같은 인스턴스에 남는다
    goToStep: (step: OnboardingStepNumber) => view.rerender(withClient(<WikiOnboardingPage step={step} />)),
  };
}

function mockSubmitHandlers(options: { maintenanceStatus?: (credentialId: number) => number } = {}) {
  const posted: RecordedRequest[] = [];
  const put: RecordedRequest[] = [];

  server.use(
    http.get('/api/v1/automations/credentials', () =>
      HttpResponse.json({ connector: 'channel_talk', total_credentials: CREDENTIALS.length, credentials: CREDENTIALS }),
    ),
    http.post('/api/v1/wiki/channels/onboarding', async ({ request }) => {
      posted.push({ url: request.url, body: await request.json() });
      return HttpResponse.json({ id: 'ch-1', name: 'CS 응대 위키' });
    }),
    http.put('/api/v1/wiki/knowledge-maintenance-settings/:credentialId', async ({ request, params }) => {
      const credentialId = Number(params.credentialId);
      put.push({ url: request.url, body: await request.json() });

      const status = options.maintenanceStatus?.(credentialId) ?? 200;
      if (status !== 200) {
        return HttpResponse.json({ code: 'FORBIDDEN', message: '권한이 없어요' }, { status });
      }
      return HttpResponse.json({
        credential_id: credentialId,
        enabled: true,
        interval_minutes: 1440,
        execution_anchor_at: '2026-08-19T00:00:00+09:00',
      });
    }),
  );

  return { posted, put };
}

/** 1단계 이름 입력 → 2단계 채널 선택까지 진행한 뒤 완료 화면을 연다 */
async function walkToCompleteStep(
  user: ReturnType<typeof userEvent.setup>,
  view: ReturnType<typeof renderOnboarding>,
  channelNames: readonly string[],
) {
  await user.type(screen.getByPlaceholderText(WIKI_NAME_FIELD.placeholder), 'CS 응대 위키');
  await user.click(screen.getByRole('button', { name: ONBOARDING_NEXT_LABEL }));
  view.goToStep(2);

  for (const channelName of channelNames) {
    await user.click(screen.getByRole('button', { name: new RegExp(CHANNEL_PICKER_PLACEHOLDER) }));
    await user.click(await screen.findByRole('menuitem', { name: channelName }));
  }

  await user.click(screen.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));
  view.goToStep(3);
}

beforeEach(() => {
  mockPush.mockClear();
  mockBack.mockClear();
  vi.mocked(toast).mockClear();
});

describe('WikiOnboardingPage 제출', () => {
  it('채널 생성 1회 뒤 고른 채널마다 수집 설정을 저장하고 대시보드로 간다', async () => {
    const user = userEvent.setup();
    const { posted, put } = mockSubmitHandlers();
    const view = renderOnboarding();

    await walkToCompleteStep(user, view, ['고객지원', '기술문의']);
    await user.click(screen.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/llm-wiki'));

    // ① 채널 생성은 한 번뿐이고, 단일 선택은 1원소 배열로 실린다
    expect(posted).toHaveLength(1);
    expect(posted[0].body).toEqual({
      name: 'CS 응대 위키',
      domain_preset: 'voc',
      purpose_presets: ['voc.top_requests'],
      kinds: ['feature_request_status'],
      style_preset: 'style.wiki_standard',
    });

    // ② 수집 설정은 고른 채널톡 credential 경로마다 한 번씩
    expect(put).toHaveLength(2);
    expect(put.map((request) => new URL(request.url).pathname)).toEqual([
      '/api/v1/wiki/knowledge-maintenance-settings/11',
      '/api/v1/wiki/knowledge-maintenance-settings/12',
    ]);

    const body = put[0].body as Record<string, unknown>;
    expect(body.enabled).toBe(true);
    expect(body.interval_minutes).toBe(1440);
    expect(body.execution_anchor_at).toMatch(/^\d{4}-\d{2}-\d{2}T00:00:00(?:[+-]\d{2}:\d{2}|Z)$/);
    // 채널마다 같은 앵커를 쓴다 — 위상이 갈리면 갱신 시각이 채널마다 어긋난다
    expect((put[1].body as Record<string, unknown>).execution_anchor_at).toBe(body.execution_anchor_at);
  });

  it('수집 설정이 일부 실패해도 채널은 이미 생겼으므로 대시보드로 보낸다', async () => {
    const user = userEvent.setup();
    const { put } = mockSubmitHandlers({ maintenanceStatus: (credentialId) => (credentialId === 12 ? 403 : 200) });
    const view = renderOnboarding();

    await walkToCompleteStep(user, view, ['고객지원', '기술문의']);
    await user.click(screen.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/llm-wiki'));
    expect(put).toHaveLength(2);

    // 실패한 채널 수와 서버 문구를 토스트로만 알린다
    await waitFor(() => expect(toast).toHaveBeenCalledWith(expect.stringContaining('채널 1개')));
    expect(vi.mocked(toast).mock.calls[0][0]).toContain('권한이 없어요');
  });

  it('채널 생성이 실패하면 수집 설정도 대시보드 이동도 없다', async () => {
    const user = userEvent.setup();
    const put: RecordedRequest[] = [];

    server.use(
      http.get('/api/v1/automations/credentials', () =>
        HttpResponse.json({ connector: 'channel_talk', total_credentials: 1, credentials: CREDENTIALS }),
      ),
      http.post('/api/v1/wiki/channels/onboarding', () =>
        HttpResponse.json({ code: 'CHANNEL_NAME_TAKEN', message: '이미 있는 이름이에요' }, { status: 409 }),
      ),
      http.put('/api/v1/wiki/knowledge-maintenance-settings/:credentialId', async ({ request }) => {
        put.push({ url: request.url, body: await request.json() });
        return HttpResponse.json({});
      }),
    );

    const view = renderOnboarding();
    await walkToCompleteStep(user, view, ['고객지원']);
    await user.click(screen.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));

    await waitFor(() => expect(toast).toHaveBeenCalledWith('이미 있는 이름이에요'));
    expect(put).toHaveLength(0);
    expect(mockPush).not.toHaveBeenCalledWith('/llm-wiki');
  });

  it('완료 화면 요약이 2단계 선택을 그대로 비춘다', async () => {
    const user = userEvent.setup();
    mockSubmitHandlers();
    const view = renderOnboarding();

    await walkToCompleteStep(user, view, ['고객지원']);

    expect(screen.getByRole('heading', { level: 3, name: '수집 설정' })).toBeInTheDocument();
    expect(screen.getByText('갱신 주기').nextElementSibling).toHaveTextContent('매일');
    expect(screen.getByText('실행시간').nextElementSibling).toHaveTextContent('자정');
    expect(screen.getByRole('cell', { name: '고객지원' })).toBeInTheDocument();

    // 표에서 "최근 수정일" 열은 제거됐다
    expect(screen.getAllByRole('columnheader')).toHaveLength(1);
    expect(screen.queryByText('최근 수정일')).not.toBeInTheDocument();
  });

  it('필수 입력 없이 완료 화면으로 바로 들어오면 제출 버튼이 잠긴다', () => {
    mockSubmitHandlers();
    const view = renderOnboarding();
    view.goToStep(3);

    expect(screen.getByRole('button', { name: ONBOARDING_FINISH_LABEL })).toBeDisabled();
  });
});
