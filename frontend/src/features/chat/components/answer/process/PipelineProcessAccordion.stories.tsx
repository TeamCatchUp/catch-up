import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, userEvent, waitFor, within } from 'storybook/test';

import { complexPipelineEvents } from '@/features/chat/__fixtures__/chatStory.fixtures';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import PipelineProcessAccordion from './PipelineProcessAccordion';

interface PipelineProcessAccordionStoryArgs {
  sourceCount: number;
  hasProcess: boolean;
}

function PipelineProcessAccordionSurface(args: PipelineProcessAccordionStoryArgs) {
  return (
    <div className="bg-fill-normal-normal flex min-h-96 items-start justify-center p-6">
      <div className="w-192.75 max-w-full">
        <PipelineProcessAccordion
          pipelineResult={args.hasProcess ? complexPipelineEvents : null}
          sourceCount={args.sourceCount}
        />
      </div>
    </div>
  );
}

const meta = {
  title: 'Compositions/Chat/Answers/PipelineProcessAccordion',
  component: PipelineProcessAccordion,
  tags: ['autodocs'],
  args: {
    sourceCount: 6,
    hasProcess: true,
  },
  argTypes: {
    sourceCount: { control: { type: 'number', min: 0 } },
    hasProcess: { control: 'boolean' },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['collapsed', 'expanded', 'fallback'],
      usedBy: ['chat'],
      interactionNotes: ['The interaction opens the accordion and verifies mapped pipeline steps.'],
    }),
  },
} satisfies Meta<PipelineProcessAccordionStoryArgs>;

export default meta;

type Story = StoryObj<PipelineProcessAccordionStoryArgs>;

export const Playground: Story = {
  render: (args) => <PipelineProcessAccordionSurface {...args} />,
};

export const ExpandInteraction: Story = {
  render: (args) => <PipelineProcessAccordionSurface {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole('button', { name: /질문과 연관된 6개의 핵심 자료/ });

    await userEvent.click(trigger);

    await expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await waitFor(() => expect(canvas.getByText('탐색 계획 수립')).toBeVisible());
    await waitFor(() => expect(canvas.getByText('2회 탐색 · 총 25건')).toBeVisible());
  },
};

export const FallbackWithoutProcess: Story = {
  args: { hasProcess: false },
  render: (args) => <PipelineProcessAccordionSurface {...args} />,
};
