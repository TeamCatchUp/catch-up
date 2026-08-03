import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorScopeTable from './ConnectorScopeTable';

const meta = {
  title: 'Compositions/Admin/Integrations/Detail/ConnectorScopeTable',
  component: ConnectorScopeTable,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134113',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134113',
      },
      viewport: { width: 720, height: 300 },
      states: ['slack', 'jira-placeholder'],
      layoutNotes: ['행 padding 14/20, gap 16, 라벨 열 고정 150px, 마지막 행을 뺀 나머지에 하단 경계선.'],
    }),
  },
} satisfies Meta<typeof ConnectorScopeTable>;

export default meta;

type Story = StoryObj<typeof ConnectorScopeTable>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Slack: Story = {
  render: (args) => (
    <Frame>
      <ConnectorScopeTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('연동 범위')).toBeInTheDocument();

    // 4행이 Figma 순서대로
    for (const label of ['무엇을', '어디까지', '언제·어떻게', '누가 볼 수 있나']) {
      await expect(canvas.getByText(label)).toBeInTheDocument();
    }
    await expect(canvas.getByText('메시지 · 스레드 · 답글 (선택한 채널의 대화)')).toBeInTheDocument();
    await expect(canvas.getByText('워크스페이스 멤버 (원본 채널 공개 범위를 따름)')).toBeInTheDocument();

    // 표로 노출한다
    await expect(canvas.getAllByRole('row')).toHaveLength(4);
  },
};

export const JiraPlaceholder: Story = {
  args: { service: 'jira' },
  render: (args) => (
    <Frame>
      <ConnectorScopeTable {...args} />
    </Frame>
  ),
};
