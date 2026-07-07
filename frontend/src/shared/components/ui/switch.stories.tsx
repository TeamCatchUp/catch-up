'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Switch } from './switch';

interface SwitchStoryArgs {
  initialChecked: boolean;
  disabled: boolean;
  label: string;
  onCheckedChange: (checked: boolean) => void;
}

function StatefulSwitch({ initialChecked, disabled, label, onCheckedChange }: SwitchStoryArgs) {
  const [checked, setChecked] = useState(initialChecked);

  return (
    <label className="bg-fill-normal-normal flex min-h-20 items-center gap-3 p-6">
      <Switch
        checked={checked}
        disabled={disabled}
        aria-label={label}
        onCheckedChange={(next) => {
          setChecked(next);
          onCheckedChange(next);
        }}
      />
      <span className="text-body-small text-text-normal-normal font-medium">{label}</span>
    </label>
  );
}

const meta = {
  title: 'Primitives/Shared/Switch',
  tags: ['autodocs'],
  args: {
    initialChecked: true,
    disabled: false,
    label: '스마트 필터',
    onCheckedChange: fn(),
  },
  argTypes: {
    initialChecked: {
      control: 'boolean',
    },
    disabled: {
      control: 'boolean',
    },
    label: {
      control: 'text',
    },
    onCheckedChange: {
      control: false,
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
      states: ['checked', 'unchecked', 'disabled'],
      interactionNotes: ['Actions log checked changes through storybook/test fn spies.'],
      usedBy: ['hybrid-search'],
    }),
  },
} satisfies Meta<SwitchStoryArgs>;

export default meta;

type Story = StoryObj<SwitchStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulSwitch key={`${args.initialChecked}:${args.disabled}`} {...args} />,
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('switch', { name: args.label }));
    await expect(args.onCheckedChange).toHaveBeenCalledWith(false);
  },
};
