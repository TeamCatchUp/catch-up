import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorScopeCompare from './ConnectorScopeCompare';

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectorScopeCompare',
  component: ConnectorScopeCompare,
  tags: ['autodocs'],
  args: { service: 'slack' },
  argTypes: {
    service: { control: 'inline-radio', options: ['slack', 'channel_talk', 'confluence', 'jira', 'github'] },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16966-26838',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16966:26838',
      },
      viewport: { width: 720, height: 260 },
      states: ['slack', 'jira-placeholder'],
      tokenNotes: [
        '연동돼요 카드 #E6FAF2 = bg-accent-green-lighten, 아이콘 칩 #D9F7EB = bg-accent-green-neutral.',
        '연동 안 돼요 카드 #FFFAFA = bg-accent-red-lighten, 아이콘 칩 #FEECEC = bg-accent-red-neutral.',
      ],
      layoutNotes: ['카드 padding 16, gap 12, radius 12. 불릿은 6px 원.'],
    }),
  },
} satisfies Meta<typeof ConnectorScopeCompare>;

export default meta;

type Story = StoryObj<typeof ConnectorScopeCompare>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Slack: Story = {
  render: (args) => (
    <Frame>
      <ConnectorScopeCompare {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('연동돼요')).toBeInTheDocument();
    await expect(canvas.getByText('연동 안 돼요')).toBeInTheDocument();

    await expect(canvas.getByText('선택한 공개 채널의 메시지 · 스레드')).toBeInTheDocument();
    await expect(canvas.getByText('DM · 그룹 DM — 봇은 초대된 채널만 읽어요')).toBeInTheDocument();

    // 목록 2개 × 항목 3개
    const lists = canvas.getAllByRole('list');
    await expect(lists).toHaveLength(2);
    await expect(canvas.getAllByRole('listitem')).toHaveLength(6);
  },
};

export const JiraPlaceholder: Story = {
  args: { service: 'jira' },
  render: (args) => (
    <Frame>
      <ConnectorScopeCompare {...args} />
    </Frame>
  ),
};
