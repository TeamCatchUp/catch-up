import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectionStatusCard from './ConnectionStatusCard';

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectionStatusCard',
  component: ConnectionStatusCard,
  tags: ['autodocs'],
  args: {
    connected: false,
    showDisconnectedIcon: true,
    useSharedSourceButton: false,
    onInstall: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['connected', 'disconnected', 'disconnected-no-install', 'channel-talk-variant'],
      reuseNotes: [
        'IntegrationManagementSection과 ChannelTalkManagementPanel에 복제돼 있던 두 벌을 합쳤다.',
      ],
      layoutNotes: [
        'VariantMatrix 스토리는 두 벌 사이의 drift 3건 중 2건(미연동 아이콘, 원문 보기 버튼)을 나란히 보여준다.',
        '이번 작업은 통일하지 않고 prop으로 현행을 재현한다 — 어느 쪽으로 합칠지는 디자이너 확인 대상.',
      ],
    }),
  },
} satisfies Meta<typeof ConnectionStatusCard>;

export default meta;

type Story = StoryObj<typeof ConnectionStatusCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-160 flex-col p-6">{children}</div>
);

export const Playground: Story = {
  render: (args) => (
    <Frame>
      <ConnectionStatusCard {...args} />
    </Frame>
  ),
};

export const Connected: Story = {
  args: { connected: true },
  render: (args) => (
    <Frame>
      <ConnectionStatusCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연동됨')).toBeInTheDocument();
    // 연동된 상태에서는 "연동하기" 진입점이 없어야 한다
    await expect(canvas.queryByRole('button', { name: '연동하기' })).not.toBeInTheDocument();
  },
};

/** GitHub·채널톡 — OAuth install 진입점이 없는 도구 */
export const DisconnectedWithoutInstall: Story = {
  args: { connected: false, onInstall: undefined },
  render: (args) => (
    <Frame>
      <ConnectionStatusCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연동 안됨')).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '연동하기' })).not.toBeInTheDocument();
  },
};

/**
 * 두 벌 사이의 drift를 나란히 놓는다.
 * 위: 일반 도구(아이콘 있음 + raw button) / 아래: 채널톡(아이콘 없음 + shared Button)
 */
export const VariantMatrix: Story = {
  render: () => (
    <Frame>
      <div className="flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <span className="text-label-xsmall text-text-normal-alternative">일반 도구 — 미연동</span>
          <ConnectionStatusCard
            connected={false}
            showDisconnectedIcon
            useSharedSourceButton={false}
            onInstall={fn()}
          />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-label-xsmall text-text-normal-alternative">
            채널톡 — 미연동 (아이콘 없음, 원문 보기가 shared Button)
          </span>
          <ConnectionStatusCard connected={false} showDisconnectedIcon={false} useSharedSourceButton />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-label-xsmall text-text-normal-alternative">연동됨 (두 벌 동일)</span>
          <ConnectionStatusCard connected showDisconnectedIcon useSharedSourceButton={false} />
        </div>
      </div>
    </Frame>
  ),
};
