import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorPreConnectDetail from './ConnectorPreConnectDetail';

const meta = {
  title: 'Compositions/Admin/Integrations/Detail/ConnectorPreConnectDetail',
  component: ConnectorPreConnectDetail,
  tags: ['autodocs'],
  args: { service: 'slack', onCheckMapping: fn(), onConnect: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134087',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134087',
      },
      viewport: { width: 780, height: 1200 },
      states: ['default', 'popover-dismissed', 'channel-talk'],
      dataNotes: [
        '문구는 전부 CONNECTOR_CONTENT에서 온다 — Jira/Github/Confluence/채널톡은 Slack 카피 복제(TODO(copy)).',
        '매핑 확인 모달은 구현하지 않는다(스펙 결정 #1) — 팝오버가 비차단 안내를 대신한다.',
        '채널톡은 가이드 아코디언이 없다(현행에도 없음).',
      ],
    }),
  },
} satisfies Meta<typeof ConnectorPreConnectDetail>;

export default meta;

type Story = StoryObj<typeof ConnectorPreConnectDetail>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195 p-8">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <ConnectorPreConnectDetail {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('연동 전, 이용자 매핑 상태를 확인해 주세요')).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '매핑 확인하기' }));
    await expect(args.onCheckMapping).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: '연결하기' }));
    await expect(args.onConnect).toHaveBeenCalled();
  },
};

export const PopoverDismissed: Story = {
  render: (args) => (
    <Frame>
      <ConnectorPreConnectDetail {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: '닫기' }));
    await expect(canvas.queryByText('연동 전, 이용자 매핑 상태를 확인해 주세요')).not.toBeInTheDocument();
  },
};

/** 채널톡은 가이드 아코디언이 없다 */
export const ChannelTalk: Story = {
  args: { service: 'channel_talk' },
  render: (args) => (
    <Frame>
      <ConnectorPreConnectDetail {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.queryByText(/연동 가이드 보기/)).not.toBeInTheDocument();
  },
};
