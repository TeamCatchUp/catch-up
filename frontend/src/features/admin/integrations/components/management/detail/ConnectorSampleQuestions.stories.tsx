import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorSampleQuestions from './ConnectorSampleQuestions';

const meta = {
  title: 'Compositions/Admin/Integrations/Detail/ConnectorSampleQuestions',
  component: ConnectorSampleQuestions,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134108',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134108',
      },
      viewport: { width: 720, height: 200 },
      states: ['slack', 'jira-placeholder'],
      dataNotes: ['Slack 외 도구는 카피 미정이라 Slack 값을 복제한 상태다 (connectorContent.ts TODO(copy)).'],
    }),
  },
} satisfies Meta<typeof ConnectorSampleQuestions>;

export default meta;

type Story = StoryObj<typeof ConnectorSampleQuestions>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Slack: Story = {
  render: (args) => (
    <Frame>
      <ConnectorSampleQuestions {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('이렇게 물어볼 수 있어요.')).toBeInTheDocument();
    await expect(canvas.getByText('"이번 주에 우리가 뭘 결정했지?"')).toBeInTheDocument();
    await expect(canvas.getByText('"답 안 달린 질문들만 모아줘"')).toBeInTheDocument();
    await expect(canvas.getByText('"이번 주 논의 요약해줘"')).toBeInTheDocument();

    // 목록으로 노출한다 — 스크린리더가 3개임을 알 수 있어야 한다
    await expect(canvas.getAllByRole('listitem')).toHaveLength(3);
  },
};

/** 카피 미정 상태 — Slack 값이 그대로 보인다 */
export const JiraPlaceholder: Story = {
  args: { service: 'jira' },
  render: (args) => (
    <Frame>
      <ConnectorSampleQuestions {...args} />
    </Frame>
  ),
};
