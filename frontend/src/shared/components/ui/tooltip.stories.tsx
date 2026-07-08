'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import InfoIcon from '@/public/icons/icon/info.svg';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Button } from './button';
import type { TooltipSize } from './tooltip';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './tooltip';

const tooltipSizes = ['sm', 'lg'] as const satisfies readonly TooltipSize[];
const tooltipSides = ['top', 'right', 'bottom', 'left'] as const;

interface TooltipStoryArgs {
  size: TooltipSize;
  side: (typeof tooltipSides)[number];
  label: string;
  description: string;
}

const meta = {
  title: 'Primitives/Shared/Tooltip',
  tags: ['autodocs'],
  args: {
    size: 'sm',
    side: 'top',
    label: '실행 조건 도움말',
    description: 'Agent가 고객 문의를 감지하는 조건을 설명합니다.',
  },
  argTypes: {
    size: {
      control: 'inline-radio',
      options: tooltipSizes,
    },
    side: {
      control: 'inline-radio',
      options: tooltipSides,
    },
    label: {
      control: 'text',
    },
    description: {
      control: 'text',
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['closed', 'hovered', 'sizes'],
      usedBy: ['agent-studio'],
      interactionNotes: ['The play function hovers the trigger and checks the portal tooltip content.'],
      reuseNotes: ['Primitive tooltip used by Agent Studio settings help text.'],
    }),
  },
} satisfies Meta<TooltipStoryArgs>;

export default meta;

type Story = StoryObj<TooltipStoryArgs>;

export const Playground: Story = {
  render: ({ size, side, label, description }) => (
    <TooltipProvider delayDuration={0}>
      <div className="bg-fill-normal-normal flex min-h-40 items-center justify-center p-6">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="icon-outline-gray" size="sm" aria-label={label}>
              <InfoIcon className="size-5" aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent size={size} side={side}>
            {description}
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await userEvent.hover(canvas.getByRole('button', { name: args.label }));
    const tooltipMatches = await portal.findAllByText(args.description);
    await expect(tooltipMatches[0]).toBeVisible();
  },
};

export const SizeSet: Story = {
  render: ({ side, label, description }) => (
    <TooltipProvider delayDuration={0}>
      <div className="bg-fill-normal-normal flex min-h-40 items-center justify-center gap-3 p-6">
        {tooltipSizes.map((size) => (
          <Tooltip key={size} defaultOpen>
            <TooltipTrigger asChild>
              <Button variant="box-outline-gray" size="sm" aria-label={`${label} ${size}`}>
                {size}
              </Button>
            </TooltipTrigger>
            <TooltipContent size={size} side={side}>
              {description}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </TooltipProvider>
  ),
};
