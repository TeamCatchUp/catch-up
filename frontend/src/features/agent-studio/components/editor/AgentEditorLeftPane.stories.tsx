import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import AgentEditorLeftPane from './AgentEditorLeftPane';

const meta = {
  title: 'Compositions/Agent Studio/Editor/AgentEditorLeftPane',
  component: AgentEditorLeftPane,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['fixture-default'],
      reuseNotes: ['Left pane is the editor preview and breadcrumb composition used by the editor screen.'],
    }),
  },
} satisfies Meta<typeof AgentEditorLeftPane>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <div className="bg-background-normal-normal h-180 overflow-hidden">
      <AgentEditorLeftPane />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('link', { name: 'Agent Studio' })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { name: '문의 대응 리포트 만들기' })).toBeInTheDocument();
  },
};
