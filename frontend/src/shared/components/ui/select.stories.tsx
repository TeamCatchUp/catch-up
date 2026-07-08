'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';

const selectOptions = [
  { value: 'channel-talk-support', label: 'CatchUp 고객 문의' },
  { value: 'channel-talk-vip', label: 'VIP 문의 채널' },
  { value: 'channel-talk-archive', label: '보관 채널', disabled: true },
] as const;

interface SelectStoryArgs {
  value: string;
  placeholder: string;
  disabled: boolean;
  onValueChange: (value: string) => void;
}

function StatefulSelect({ value: initialValue, placeholder, disabled, onValueChange }: SelectStoryArgs) {
  const [value, setValue] = useState(initialValue);

  return (
    <div className="bg-fill-normal-normal flex min-h-40 items-start p-6">
      <div className="w-80">
        <Select
          value={value}
          disabled={disabled}
          onValueChange={(next) => {
            setValue(next);
            onValueChange(next);
          }}
        >
          <SelectTrigger aria-label="채널 선택">
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {selectOptions.map((option) => (
              <SelectItem key={option.value} value={option.value} disabled={option.disabled}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

const meta = {
  title: 'Primitives/Shared/Select',
  tags: ['autodocs'],
  args: {
    value: '',
    placeholder: '채널을 선택해주세요',
    disabled: false,
    onValueChange: fn(),
  },
  argTypes: {
    value: {
      control: 'select',
      options: ['', ...selectOptions.map((option) => option.value)],
    },
    placeholder: {
      control: 'text',
    },
    disabled: {
      control: 'boolean',
    },
    onValueChange: {
      control: false,
    },
  },
  render: (args) => <StatefulSelect key={`${args.value}:${args.disabled}`} {...args} />,
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['placeholder', 'selected', 'disabled'],
      usedBy: ['agent-studio'],
      interactionNotes: ['The play function opens the portal menu and selects one option.'],
      reuseNotes: ['Primitive select used by Agent Studio field compositions.'],
    }),
  },
} satisfies Meta<SelectStoryArgs>;

export default meta;

type Story = StoryObj<SelectStoryArgs>;

export const Playground: Story = {
  play: async ({ args, canvasElement, step, userEvent }) => {
    if (args.disabled) return;

    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open select menu', async () => {
      await userEvent.click(canvas.getByRole('combobox', { name: '채널 선택' }));
      await expect(await portal.findByRole('option', { name: 'CatchUp 고객 문의' })).toBeInTheDocument();
    });

    await step('choose support channel', async () => {
      await userEvent.click(portal.getByRole('option', { name: 'CatchUp 고객 문의' }));
      await expect(args.onValueChange).toHaveBeenCalledWith('channel-talk-support');
    });
  },
};

export const Disabled: Story = {
  args: {
    value: 'channel-talk-support',
    disabled: true,
  },
};
