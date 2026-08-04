import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, fn, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import type { ConnectionStatusResponse } from '../../../types/connectionStatusApi';
import type { SyncTargetsResponse } from '../../../types/syncModel';
import EmbeddingModal from './EmbeddingModal';

// fixture는 types/connectionStatusApi.ts·types/syncModel.ts를 읽고 필드를 정확히 맞췄다.
// targets 5건: 4건 is_accessible=true(#general, #ops-alerts, #dev-team, #ops-standup) + 1건 false(#private-locked).
// display_name에 검색어 'ops'가 #ops-alerts·#ops-standup 2건에만 들어가 검색-무시 규칙 play를 가능하게 한다.

const connectionStatusFixture: ConnectionStatusResponse = {
  vendor: 'slack',
  connection_type: 'oauth_token',
  connected: true,
  count: 1,
  items: [
    {
      id: 'scope-slack-1',
      name: 'Catch Up Workspace',
      connected_at: '2026-06-01T00:00:00Z',
      metadata: { bot_user_id: 'U0123ABCD', scopes: ['channels:read', 'chat:write'] },
    },
  ],
};

const noScopeConnectionStatusFixture: ConnectionStatusResponse = {
  vendor: 'slack',
  connection_type: 'oauth_token',
  connected: false,
  count: 0,
  items: [],
};

const targetsFixture: SyncTargetsResponse = {
  connector: 'slack',
  scope_id: 'scope-slack-1',
  total_targets: 5,
  targets: [
    { target_id: 'ch-1', display_name: '#general', target_type: 'channel', is_accessible: true, metadata: {} },
    { target_id: 'ch-2', display_name: '#ops-alerts', target_type: 'channel', is_accessible: true, metadata: {} },
    { target_id: 'ch-3', display_name: '#dev-team', target_type: 'channel', is_accessible: true, metadata: {} },
    { target_id: 'ch-4', display_name: '#ops-standup', target_type: 'channel', is_accessible: true, metadata: {} },
    {
      target_id: 'ch-5',
      display_name: '#private-locked',
      target_type: 'channel',
      is_accessible: false,
      metadata: {},
    },
  ],
};

const embeddingModalHandlers = [
  http.get(API.integrations.connectionStatus('slack'), () => HttpResponse.json(connectionStatusFixture)),
  http.get(API.sync.targets, () => HttpResponse.json(targetsFixture)),
];

const meta = {
  title: 'Compositions/Admin/Integrations/Modals/EmbeddingModal',
  component: EmbeddingModal,
  tags: ['autodocs'],
  args: { open: true, onOpenChange: fn(), service: 'slack', serviceName: 'Slack', onJobStart: fn() },
  parameters: {
    msw: { handlers: embeddingModalHandlers },
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['default', 'no-scope'],
      dataNotes: [
        '기본 기간은 3년 — 모달엔 전체 옵션 자체가 없다 (EmbeddingModal.tsx:22-24).',
        '전체 선택하기는 검색 필터를 무시하고 접근 가능 전체를 선택한다 (EmbeddingModal.tsx:65-83).',
      ],
    }),
  },
} satisfies Meta<typeof EmbeddingModal>;

export default meta;

type Story = StoryObj<typeof EmbeddingModal>;

/** 기본 진입 — 기간 기본값(3년, '전체' 없음) + 검색 무시하고 접근 가능 전체 선택 */
export const Default: Story = {
  play: async ({ userEvent }) => {
    const portal = within(document.body);

    await expect(portal.getByText('임베딩 할 Slack Channel 선택하기')).toBeInTheDocument();

    // 기간 버튼: 모달 전용 옵션(전체 제외), 기본 선택은 3년
    await expect(portal.queryByRole('button', { name: '전체' })).not.toBeInTheDocument();
    await expect(portal.getByRole('button', { name: '3년' })).toHaveClass('bg-accent-black-lighten');

    // 목록이 로드될 때까지 대기 (isScopeLoading/isTargetsLoading 스켈레톤 통과)
    await portal.findByText('#general');

    // 검색어 'ops' → accessible 4건 중 2건만 표시
    const searchInput = portal.getByPlaceholderText('검색어를 입력하세요.');
    await userEvent.type(searchInput, 'ops');
    await expect(portal.getByText('#ops-alerts')).toBeInTheDocument();
    await expect(portal.getByText('#ops-standup')).toBeInTheDocument();
    await expect(portal.queryByText('#general')).not.toBeInTheDocument();

    // 전체 선택하기는 검색 필터를 무시하고 accessible 4건 전체를 선택한다
    await userEvent.click(portal.getByRole('button', { name: '전체 선택하기' }));
    await expect(portal.getByText('4개 선택됨')).toBeInTheDocument();
  },
};

/** 연동된 scope 없음 — 안내 문구만 남고 임베딩하기는 disabled */
export const NoScope: Story = {
  parameters: {
    msw: {
      handlers: [
        http.get(API.integrations.connectionStatus('slack'), () => HttpResponse.json(noScopeConnectionStatusFixture)),
      ],
    },
  },
  play: async () => {
    const portal = within(document.body);

    await expect(await portal.findByText(/연동된 Slack이\(가\) 없습니다/)).toBeInTheDocument();
    await expect(portal.getByRole('button', { name: '임베딩하기' })).toBeDisabled();
  },
};
