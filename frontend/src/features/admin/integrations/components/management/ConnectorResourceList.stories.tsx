import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { ConnectorResource } from '../../types/integrationModel';
import ConnectorResourceList from './ConnectorResourceList';

const sample = (count: number): ConnectorResource[] =>
  Array.from({ length: count }, (_, i) => ({
    name: `PROJECT-${i + 1}`,
    dateRange: '2026. 1. 1. ~ 2026. 7. 30.',
  }));

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/ConnectorResourceList',
  component: ConnectorResourceList,
  tags: ['autodocs'],
  args: {
    service: 'jira',
    resourceLabel: '임베딩된 Jira Project',
    resources: sample(3),
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['default', 'empty', 'pagination', 'long-text'],
      dataNotes: ['빈 상태 문구 "연동된 항목이 없습니다."는 감사의 UNKNOWN(구현 승계 확인) 항목이라 변경 금지.'],
    }),
  },
} satisfies Meta<typeof ConnectorResourceList>;

export default meta;

type Story = StoryObj<typeof ConnectorResourceList>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex min-h-96 w-160 flex-col p-6">{children}</div>
);

export const Playground: Story = {
  render: (args) => (
    <Frame>
      <ConnectorResourceList {...args} />
    </Frame>
  ),
};

export const Empty: Story = {
  args: { resources: [] },
  render: (args) => (
    <Frame>
      <ConnectorResourceList {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연동된 항목이 없습니다.')).toBeInTheDocument();
  },
};

export const Pagination: Story = {
  args: { resources: sample(23) },
  render: (args) => (
    <Frame>
      <ConnectorResourceList {...args} />
    </Frame>
  ),
};

export const LongText: Story = {
  args: {
    resources: [
      {
        name: '아주 긴 프로젝트 이름이 들어가는 경우 잘림 처리가 되는지 확인하기 위한 리소스 항목입니다',
        dateRange: '2026. 1. 1. ~ 2026. 7. 30.',
      },
    ],
  },
  render: (args) => (
    <Frame>
      <ConnectorResourceList {...args} />
    </Frame>
  ),
};
