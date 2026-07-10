import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { complexPipelineEvents } from '@/features/chat/__fixtures__/chatStory.fixtures';
import { buildInlineSteps } from '@/features/chat/utils/process/buildInlineSteps';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import PipelineStepItem from './PipelineStepItem';

type PipelineStepPreset = 'supervisor' | 'rewrite' | 'complex_planner' | 'search' | 'done';

interface PipelineStepItemStoryArgs {
  preset: PipelineStepPreset;
  isLast: boolean;
}

const presetOptions: readonly PipelineStepPreset[] = ['supervisor', 'rewrite', 'complex_planner', 'search', 'done'];
const steps = buildInlineSteps(complexPipelineEvents);
const stepFixtures = Object.fromEntries(steps.map((step) => [step.kind, step]));

function PipelineStepItemSurface(args: PipelineStepItemStoryArgs) {
  const step = stepFixtures[args.preset];

  if (!step) return null;

  return (
    <div className="bg-fill-normal-normal flex min-h-40 items-start justify-center p-6">
      <div className="w-160 max-w-full">
        <PipelineStepItem step={step} isLast={args.isLast} />
      </div>
    </div>
  );
}

const meta = {
  title: 'Primitives/Chat/Answers/PipelineStepItem',
  component: PipelineStepItem,
  tags: ['autodocs'],
  args: {
    preset: 'complex_planner',
    isLast: false,
  },
  argTypes: {
    preset: { control: 'select', options: presetOptions },
    isLast: { control: 'boolean' },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['request', 'rewrite', 'plan', 'search', 'done', 'connector'],
      usedBy: ['chat'],
      dataNotes: ['Step fixtures are produced by the production buildInlineSteps mapper.'],
    }),
  },
} satisfies Meta<PipelineStepItemStoryArgs>;

export default meta;

type Story = StoryObj<PipelineStepItemStoryArgs>;

export const Playground: Story = {
  render: (args) => <PipelineStepItemSurface {...args} />,
};

export const StepVariants: Story = {
  render: () => (
    <div className="bg-fill-normal-normal flex min-h-120 items-start justify-center p-6">
      <div className="w-160 max-w-full">
        {steps.map((step, index) => (
          <PipelineStepItem key={step.kind} step={step} isLast={index === steps.length - 1} />
        ))}
      </div>
    </div>
  ),
};
