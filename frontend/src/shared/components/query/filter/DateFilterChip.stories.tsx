'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import DateFilterChip from './DateFilterChip';

type DateChipPreset = 'empty' | 'april-range' | 'single-day';

interface DateFilterChipStoryArgs {
  preset: DateChipPreset;
  preserveInputFocus: boolean;
  defaultOpen: boolean;
  onChange: (next: DateRange | undefined) => void;
  onOpenChange: (open: boolean) => void;
}

const dateChipPresetOptions: readonly DateChipPreset[] = ['empty', 'april-range', 'single-day'];

const dateChipFixtures = {
  empty: undefined,
  'april-range': {
    from: new Date(2026, 3, 7),
    to: new Date(2026, 3, 20),
  },
  'single-day': {
    from: new Date(2026, 4, 11),
    to: new Date(2026, 4, 11),
  },
} satisfies Record<DateChipPreset, DateRange | undefined>;

function StatefulDateFilterChip({
  preset,
  preserveInputFocus,
  defaultOpen,
  onChange,
  onOpenChange,
}: DateFilterChipStoryArgs) {
  const [value, setValue] = useState<DateRange | undefined>(dateChipFixtures[preset]);

  return (
    <div className="bg-fill-normal-normal flex min-h-96 items-start p-6">
      <DateFilterChip
        value={value}
        activeMaxWidthClassName="max-w-45"
        preserveInputFocus={preserveInputFocus}
        defaultOpen={defaultOpen}
        onOpenChange={onOpenChange}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Query/DateFilterChip',
  tags: ['autodocs'],
  args: {
    preset: 'empty',
    preserveInputFocus: false,
    defaultOpen: false,
    onChange: fn(),
    onOpenChange: fn(),
  },
  argTypes: {
    preset: {
      control: 'select',
      options: dateChipPresetOptions,
    },
    preserveInputFocus: {
      control: 'boolean',
    },
    defaultOpen: {
      control: 'boolean',
    },
    onChange: {
      control: false,
    },
    onOpenChange: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['empty', 'range-selected', 'single-day'],
      interactionNotes: ['The play function opens the date popover, selects today, and applies the range.'],
      usedBy: ['home-docs', 'hybrid-search'],
    }),
  },
} satisfies Meta<DateFilterChipStoryArgs>;

export default meta;

type Story = StoryObj<DateFilterChipStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulDateFilterChip key={`${args.preset}:${args.defaultOpen}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open date filter chip', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '날짜 필터' }));
      await expect(args.onOpenChange).toHaveBeenCalledWith(true);
      await expect(await portal.findByRole('button', { name: '오늘 선택' })).toBeInTheDocument();
    });

    await step('select today and apply', async () => {
      await userEvent.click(portal.getByRole('button', { name: '오늘 선택' }));
      await userEvent.click(portal.getByRole('button', { name: '적용' }));
      await expect(args.onChange).toHaveBeenCalled();
    });
  },
};
