import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorErrorNotice from './ConnectorErrorNotice';

const meta = {
  title: 'Compositions/Admin/Integrations/States/ConnectorErrorNotice',
  component: ConnectorErrorNotice,
  tags: ['autodocs'],
  args: {
    serviceName: 'Jira',
  },
  argTypes: {
    serviceName: {
      control: 'inline-radio',
      options: ['Jira', 'Github', 'Slack', 'Confluence', '채널톡'],
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'error',
      designSource: 'dev-preview',
      states: ['fetch-error'],
      dataNotes: [
        '카피는 ChannelTalkManagementPanel의 현행 문구에서 도구명만 파라미터화했다.',
        'serviceName="채널톡"일 때 기존 렌더와 글자 단위로 일치해야 한다.',
      ],
    }),
  },
} satisfies Meta<typeof ConnectorErrorNotice>;

export default meta;

type Story = StoryObj<typeof ConnectorErrorNotice>;

export const Playground: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-40 w-160 flex-col p-6">
      <ConnectorErrorNotice {...args} />
    </div>
  ),
};

// 회귀 방지 — 채널톡 문구가 기존과 어긋나면 실패한다
export const ChannelTalkCopyParity: Story = {
  args: {
    serviceName: '채널톡',
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-40 w-160 flex-col p-6">
      <ConnectorErrorNotice {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      canvas.getByText('채널톡 연동 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.'),
    ).toBeInTheDocument();
  },
};

export const LongServiceName: Story = {
  args: {
    serviceName: 'Confluence',
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-40 w-80 flex-col p-6">
      <ConnectorErrorNotice {...args} />
    </div>
  ),
};
