'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SmartFilterControl from './SmartFilterControl';

interface SmartFilterControlStoryArgs {
  initialChecked: boolean;
  tone: 'primary' | 'neutral';
  description: string;
  onCheckedChange: (checked: boolean) => void;
}

function StatefulSmartFilterControl({
  initialChecked,
  tone,
  description,
  onCheckedChange,
}: SmartFilterControlStoryArgs) {
  const [checked, setChecked] = useState(initialChecked);

  return (
    <div className="bg-fill-normal-normal flex min-h-24 items-center p-6">
      <SmartFilterControl
        checked={checked}
        tone={tone}
        description={description}
        onCheckedChange={(next) => {
          setChecked(next);
          onCheckedChange(next);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Query/SmartFilterControl',
  tags: ['autodocs'],
  args: {
    initialChecked: true,
    tone: 'primary',
    description: '자동으로 적용되는 검색 필터',
    onCheckedChange: fn(),
  },
  argTypes: {
    initialChecked: {
      control: 'boolean',
    },
    tone: {
      control: 'inline-radio',
      options: ['primary', 'neutral'],
    },
    description: {
      control: 'text',
    },
    onCheckedChange: {
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
      states: ['checked', 'unchecked', 'primary-tone', 'neutral-tone'],
      interactionNotes: ['The play function toggles the underlying switch and logs the state change.'],
      usedBy: ['home-docs', 'hybrid-search'],
    }),
  },
} satisfies Meta<SmartFilterControlStoryArgs>;

export default meta;

type Story = StoryObj<SmartFilterControlStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulSmartFilterControl key={`${args.initialChecked}:${args.tone}`} {...args} />,
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('switch', { name: '스마트 필터' }));
    await expect(args.onCheckedChange).toHaveBeenCalledWith(false);
  },
};
