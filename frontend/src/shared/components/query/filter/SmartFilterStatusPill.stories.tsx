'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SmartFilterStatusPill from './SmartFilterStatusPill';

interface SmartFilterStatusPillStoryArgs {
  enabled: boolean;
  onApplyClick: () => void;
}

const meta = {
  title: 'Compositions/Shared/Query/SmartFilterStatusPill',
  tags: ['autodocs'],
  args: {
    enabled: false,
    onApplyClick: fn(),
  },
  argTypes: {
    enabled: {
      control: 'boolean',
    },
    onApplyClick: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      figmaLab: {
        caseId: 'smart-filter-status-pill',
        groupId: 'shared-query-filter',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-63671&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14308:63671',
      },
      viewport: {
        width: 520,
        height: 104,
      },
      states: ['applied', 'basic'],
      usedBy: ['hybrid-search'],
      reuseNotes: [
        'Basic state reuses Button text-primary-blue for the inline apply action.',
        'Both states reuse SmartFilterInfoTooltip for status explanation.',
      ],
      interactionNotes: ['Actions log the basic-state apply click through storybook/test fn spies.'],
      tokenNotes: [
        'Figma Fill/Normal/Strong maps to bg-fill-normal-strong.',
        'Figma Icon/Normal/Neutral maps to text-icon-normal-neutral.',
      ],
    }),
  },
} satisfies Meta<SmartFilterStatusPillStoryArgs>;

export default meta;

type Story = StoryObj<SmartFilterStatusPillStoryArgs>;

export const Playground: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-24 items-center p-6">
      <SmartFilterStatusPill enabled={args.enabled} onApplyClick={args.onApplyClick} />
    </div>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('click apply action in basic state', async () => {
      if (args.enabled) {
        await expect(canvas.getByText('스마트 필터 적용됨')).toBeInTheDocument();
        return;
      }

      await userEvent.click(canvas.getByRole('button', { name: '스마트 필터 적용하기' }));
      await expect(args.onApplyClick).toHaveBeenCalled();
    });
  },
};

export const StateSet: Story = {
  args: {
    onApplyClick: fn(),
  },
  render: ({ onApplyClick }) => (
    <div className="bg-fill-normal-normal flex min-h-24 flex-wrap items-center gap-5 p-6">
      <SmartFilterStatusPill enabled onApplyClick={onApplyClick} />
      <SmartFilterStatusPill enabled={false} onApplyClick={onApplyClick} />
    </div>
  ),
};
