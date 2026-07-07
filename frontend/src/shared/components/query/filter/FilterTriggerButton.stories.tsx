'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconFile from '@/public/icons/icon/file.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import FilterTriggerButton from './FilterTriggerButton';

interface FilterTriggerButtonStoryArgs {
  active: boolean;
  open: boolean;
  label: string;
  valueLabel: string;
  onClick: () => void;
}

const meta = {
  title: 'Compositions/Shared/Query/FilterTriggerButton',
  tags: ['autodocs'],
  args: {
    active: false,
    open: false,
    label: '검색 범위',
    valueLabel: 'Github, Slack',
    onClick: fn(),
  },
  argTypes: {
    active: {
      control: 'boolean',
    },
    open: {
      control: 'boolean',
    },
    label: {
      control: 'text',
    },
    valueLabel: {
      control: 'text',
    },
    onClick: {
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
      designSource: 'figma',
      states: ['inactive', 'active', 'open'],
      interactionNotes: ['Actions log trigger clicks through storybook/test fn spies.'],
      usedBy: ['home-docs', 'hybrid-search'],
    }),
  },
} satisfies Meta<FilterTriggerButtonStoryArgs>;

export default meta;

type Story = StoryObj<FilterTriggerButtonStoryArgs>;

export const Playground: Story = {
  render: ({ valueLabel, ...args }) => (
    <div className="bg-fill-normal-normal flex min-h-20 items-center p-6">
      <FilterTriggerButton {...args} valueLabel={args.active ? valueLabel : undefined} Icon={IconFile} />
    </div>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: args.label }));
    await expect(args.onClick).toHaveBeenCalled();
  },
};

export const ActiveSet: Story = {
  args: {
    onClick: fn(),
  },
  render: ({ label, valueLabel, onClick }) => (
    <div className="bg-fill-normal-normal flex flex-wrap items-center gap-3 p-6">
      <FilterTriggerButton active={false} label={label} open={false} Icon={IconFile} onClick={onClick} />
      <FilterTriggerButton active label={label} valueLabel={valueLabel} open={false} Icon={IconFile} onClick={onClick} />
      <FilterTriggerButton active label={label} valueLabel={valueLabel} open Icon={IconFile} onClick={onClick} />
    </div>
  ),
};
