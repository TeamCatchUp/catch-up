'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { DateRangePicker } from './date-range-picker';

type DateRangePreset = 'empty' | 'april-range' | 'single-day';

interface DateRangePickerStoryArgs {
  preset: DateRangePreset;
  numberOfMonths: 1 | 2;
  align: 'start' | 'end';
  onChange: (range: DateRange | undefined) => void;
}

const dateRangePresetOptions: readonly DateRangePreset[] = ['empty', 'april-range', 'single-day'];

const dateRangeFixtures = {
  empty: undefined,
  'april-range': {
    from: new Date(2026, 3, 7),
    to: new Date(2026, 3, 20),
  },
  'single-day': {
    from: new Date(2026, 4, 11),
    to: new Date(2026, 4, 11),
  },
} satisfies Record<DateRangePreset, DateRange | undefined>;

function StatefulDateRangePicker({ preset, numberOfMonths, align, onChange }: DateRangePickerStoryArgs) {
  const [value, setValue] = useState<DateRange | undefined>(dateRangeFixtures[preset]);

  return (
    <div className="bg-fill-normal-normal flex min-h-96 items-start p-6">
      <DateRangePicker
        value={value}
        numberOfMonths={numberOfMonths}
        align={align}
        onChange={(next) => {
          setValue(next);
          onChange(next);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Date/DateRangePicker',
  tags: ['autodocs'],
  args: {
    preset: 'empty',
    numberOfMonths: 2,
    align: 'start',
    onChange: fn(),
  },
  argTypes: {
    preset: {
      control: 'select',
      options: dateRangePresetOptions,
    },
    numberOfMonths: {
      control: 'inline-radio',
      options: [1, 2],
    },
    align: {
      control: 'inline-radio',
      options: ['start', 'end'],
    },
    onChange: {
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
      designSource: 'dev-preview',
      states: ['empty', 'range-selected', 'single-day'],
      interactionNotes: ['The play function opens the picker, selects today, and applies the temporary range.'],
      usedBy: ['home-docs', 'hybrid-search'],
    }),
  },
} satisfies Meta<DateRangePickerStoryArgs>;

export default meta;

type Story = StoryObj<DateRangePickerStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulDateRangePicker key={`${args.preset}:${args.numberOfMonths}:${args.align}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open date range picker', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '날짜를 선택하세요' }));
      await expect(await portal.findByRole('button', { name: '오늘 선택' })).toBeInTheDocument();
    });

    await step('select today and apply', async () => {
      await userEvent.click(portal.getByRole('button', { name: '오늘 선택' }));
      await userEvent.click(portal.getByRole('button', { name: '적용' }));
      await expect(args.onChange).toHaveBeenCalled();
    });
  },
};
