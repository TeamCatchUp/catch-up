import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import type { ConnectorDetailStatus } from '../../../types/integrationModel';
import ConnectorStateBoundary from './ConnectorStateBoundary';

const statusOptions: readonly ConnectorDetailStatus[] = ['loading', 'error', 'ready'];

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectorStateBoundary',
  component: ConnectorStateBoundary,
  tags: ['autodocs'],
  args: {
    status: 'ready',
    serviceName: 'Jira',
  },
  argTypes: {
    status: {
      control: 'inline-radio',
      options: statusOptions,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['loading', 'error', 'ready'],
      reuseNotes: ['5개 도구 전부가 이 경계를 통과한다 — 도구별 로딩·오류 처리 불일치를 구조적으로 막는다.'],
    }),
  },
} satisfies Meta<typeof ConnectorStateBoundary>;

export default meta;

type Story = StoryObj<typeof ConnectorStateBoundary>;

const Body = () => (
  <div className="border-line-normal-assistive bg-fill-normal-strong text-body-small text-text-normal-normal rounded-xl border px-4 py-3">
    상세 본문
  </div>
);

export const Playground: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 w-160 flex-col p-6">
      <ConnectorStateBoundary {...args}>
        <Body />
      </ConnectorStateBoundary>
    </div>
  ),
};

export const Loading: Story = {
  args: { status: 'loading' },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 w-160 flex-col p-6">
      <ConnectorStateBoundary {...args}>
        <Body />
      </ConnectorStateBoundary>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByLabelText('연동 정보 불러오는 중')).toBeInTheDocument();
    await expect(canvas.queryByText('상세 본문')).not.toBeInTheDocument();
  },
};

export const Error: Story = {
  args: { status: 'error', serviceName: 'Jira' },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 w-160 flex-col p-6">
      <ConnectorStateBoundary {...args}>
        <Body />
      </ConnectorStateBoundary>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      canvas.getByText('Jira 연동 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.'),
    ).toBeInTheDocument();
    // 조회 실패가 "연동된 항목이 없습니다."로 보이지 않아야 한다
    await expect(canvas.queryByText('상세 본문')).not.toBeInTheDocument();
  },
};

export const Ready: Story = {
  args: { status: 'ready' },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 w-160 flex-col p-6">
      <ConnectorStateBoundary {...args}>
        <Body />
      </ConnectorStateBoundary>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('상세 본문')).toBeInTheDocument();
  },
};
