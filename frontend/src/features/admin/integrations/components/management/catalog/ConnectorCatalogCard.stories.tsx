import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorCatalogCard from './ConnectorCatalogCard';

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectorCatalogCard',
  component: ConnectorCatalogCard,
  tags: ['autodocs'],
  args: { service: 'slack', connected: false, onConnect: fn() },
  argTypes: {
    service: {
      control: 'inline-radio',
      options: ['slack', 'channel_talk', 'confluence', 'jira', 'github'],
    },
    connected: { control: 'boolean' },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134207',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134207',
      },
      viewport: { width: 400, height: 200 },
      states: ['default', 'connected', 'channel-talk'],
      dataNotes: ['문구는 constants/connectorContent.ts에서 온다 — 컴포넌트가 문구를 갖지 않는다.'],
      tokenNotes: ['로고 칩 40px / 로고 28px / padding 16 — Figma 16922:134217 실측.'],
    }),
  },
} satisfies Meta<typeof ConnectorCatalogCard>;

export default meta;

type Story = StoryObj<typeof ConnectorCatalogCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-87.5 p-4">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <ConnectorCatalogCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('Slack')).toBeInTheDocument();
    await expect(canvas.getByText('채팅에 흩어진 결정과 답을 다시 찾아요')).toBeInTheDocument();

    const button = canvas.getByRole('button', { name: '연결' });
    await expect(button).toBeEnabled();

    await userEvent.click(button);
    await expect(args.onConnect).toHaveBeenCalledWith('slack');
  },
};

export const Connected: Story = {
  args: { connected: true },
  render: (args) => (
    <Frame>
      <ConnectorCatalogCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 이미 연결된 도구는 비활성으로 남는다 (Figma 17125:115134)
    await expect(canvas.getByRole('button', { name: /연결됨/ })).toBeDisabled();
  },
};

export const ChannelTalk: Story = {
  args: { service: 'channel_talk' },
  render: (args) => (
    <Frame>
      <ConnectorCatalogCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('채널톡')).toBeInTheDocument();
    await expect(canvas.getByText('상담 이력에서 문의 대응에 필요한 답 찾기')).toBeInTheDocument();
  },
};
