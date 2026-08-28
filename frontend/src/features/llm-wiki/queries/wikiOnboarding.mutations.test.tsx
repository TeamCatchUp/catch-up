import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { KnowledgeMaintenanceSettingRequest, WikiChannelOnboardingRequest } from '../api/onboardingDto';
import { buildMaintenanceFailureText } from '../fixtures/llmWikiOnboardingFixtures';
import { wikiQueries } from './wiki.queries';
import { useWikiOnboardingSubmitMutation } from './wikiOnboarding.mutations';

const onboardingApi = vi.hoisted(() => ({
  createWikiChannelByOnboarding: vi.fn(),
  updateKnowledgeMaintenanceSetting: vi.fn(),
}));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 호출 순서·횟수와 부분 실패 처리다
vi.mock('../api/onboardingRequests', () => onboardingApi);
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

const CHANNEL_REQUEST: WikiChannelOnboardingRequest = {
  name: '결제',
  domain_preset: 'commerce',
  purpose_presets: ['incident'],
  kinds: ['incident_guide'],
  style_preset: 'concise',
};
const MAINTENANCE: KnowledgeMaintenanceSettingRequest = {
  enabled: true,
  interval_minutes: 60,
  execution_anchor_at: '2026-08-19T09:00:00+09:00',
};
const CHANNEL_RESPONSE = { id: 'ch-1', name: '결제' };

/** parseApiError가 읽는 최소 형태의 axios 에러 */
const apiError = (code: string, message: string) => ({
  isAxiosError: true,
  response: { data: { detail: { code, message } } },
});

const createHarness = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const spy = vi.spyOn(client, 'invalidateQueries');

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  return { wrapper, invalidatedKeys: () => spy.mock.calls.map(([filters]) => filters?.queryKey) };
};

const settingResponse = (credentialId: number) => ({ credential_id: credentialId, ...MAINTENANCE });

beforeEach(() => {
  vi.clearAllMocks();
  onboardingApi.createWikiChannelByOnboarding.mockResolvedValue(CHANNEL_RESPONSE);
  onboardingApi.updateKnowledgeMaintenanceSetting.mockImplementation((credentialId: number) =>
    Promise.resolve(settingResponse(credentialId)),
  );
});

describe('useWikiOnboardingSubmitMutation 성공 경로', () => {
  it('채널을 만든 뒤 고른 credential마다 같은 수집 설정을 한 번씩 저장한다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [11, 22], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(onboardingApi.createWikiChannelByOnboarding).toHaveBeenCalledExactlyOnceWith(CHANNEL_REQUEST);
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).toHaveBeenCalledTimes(2);
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).toHaveBeenCalledWith(11, MAINTENANCE);
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).toHaveBeenCalledWith(22, MAINTENANCE);
  });

  it('credential을 하나도 고르지 않으면 설정 저장을 아예 부르지 않는다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).not.toHaveBeenCalled();
    expect(result.current.data).toEqual({ channel: CHANNEL_RESPONSE, failedCredentialCount: 0, failureMessage: null });
  });

  it('성공하면 위키 뿌리를 무효화한다 — 채널이 생겨 대시보드·SNB 트리가 바뀐다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [11], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([wikiQueries.all()]);
  });

  it('전부 성공하면 알림을 띄우지 않는다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [11, 22], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toastMock).not.toHaveBeenCalled();
  });
});

describe('useWikiOnboardingSubmitMutation 부분 실패', () => {
  beforeEach(() => {
    onboardingApi.updateKnowledgeMaintenanceSetting.mockImplementation((credentialId: number) => {
      if (credentialId === 22) return Promise.reject(apiError('INVALID_ANCHOR', '앵커 시각이 올바르지 않아요.'));
      if (credentialId === 33) return Promise.reject(apiError('FORBIDDEN', '권한이 없어요.'));
      return Promise.resolve(settingResponse(credentialId));
    });
  });

  it('설정 저장이 일부 실패해도 되돌리지 않고 성공으로 끝낸다 — 채널은 이미 만들어졌다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [11, 22, 33], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      channel: CHANNEL_RESPONSE,
      failedCredentialCount: 2,
      failureMessage: '앵커 시각이 올바르지 않아요.',
    });
  });

  it('실패가 있어도 나머지 credential 저장은 끝까지 간다 — 첫 실패에서 멈추지 않는다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [22, 11], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).toHaveBeenCalledTimes(2);
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).toHaveBeenCalledWith(11, MAINTENANCE);
  });

  it('부분 실패에도 위키 뿌리는 무효화하고 실패 수와 첫 문구로 알린다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [11, 22, 33], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([wikiQueries.all()]);
    expect(toastMock).toHaveBeenCalledWith(buildMaintenanceFailureText(2, '앵커 시각이 올바르지 않아요.'));
  });
});

describe('useWikiOnboardingSubmitMutation 채널 생성 실패', () => {
  it('채널이 만들어지지 않으면 설정 저장을 시도하지 않고 캐시도 건드리지 않는다', async () => {
    onboardingApi.createWikiChannelByOnboarding.mockRejectedValue(
      apiError('DUPLICATE_NAME', '같은 이름의 채널이 있어요.'),
    );
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useWikiOnboardingSubmitMutation(), { wrapper });

    result.current.mutate({ channel: CHANNEL_REQUEST, credentialIds: [11, 22], maintenance: MAINTENANCE });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(onboardingApi.updateKnowledgeMaintenanceSetting).not.toHaveBeenCalled();
    expect(toastMock).toHaveBeenCalledWith('같은 이름의 채널이 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});
