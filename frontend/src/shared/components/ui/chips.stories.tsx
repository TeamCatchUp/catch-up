'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import CheckIcon from '@/public/icons/icon/check.svg';
import CloseIcon from '@/public/icons/icon/close.svg';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Chip, ChipGroup } from './chips';

const chipVariants = ['square', 'capsule', 'outline'] as const;

interface ChipStoryArgs {
  variant: (typeof chipVariants)[number];
  mode: 'single' | 'multi';
  initialValue: string;
  showLeadingIcon: boolean;
  showTrailingIcon: boolean;
  onChange: (value: string | string[]) => void;
}

const chipItems = [
  { value: 'inbox', label: '고객 문의' },
  { value: 'vip', label: 'VIP' },
  { value: 'handoff', label: '상담원 연결' },
] as const;

function StatefulChipGroup(args: ChipStoryArgs) {
  const [singleValue, setSingleValue] = useState(args.initialValue);
  const [multiValue, setMultiValue] = useState<string[]>(args.initialValue ? [args.initialValue] : []);
  const value = args.mode === 'single' ? singleValue : multiValue;

  return (
    <div className="bg-fill-normal-normal flex min-h-32 items-center p-6">
      <ChipGroup
        mode={args.mode}
        value={value}
        onChange={(next) => {
          if (Array.isArray(next)) {
            setMultiValue(next);
          } else {
            setSingleValue(next);
          }
          args.onChange(next);
        }}
      >
        {chipItems.map((item) => (
          <Chip
            key={item.value}
            value={item.value}
            variant={args.variant}
            leadingIcon={args.showLeadingIcon ? <CheckIcon aria-hidden="true" /> : undefined}
            trailingIcon={args.showTrailingIcon ? <CloseIcon aria-hidden="true" /> : undefined}
          >
            {item.label}
          </Chip>
        ))}
      </ChipGroup>
    </div>
  );
}

const meta = {
  title: 'Primitives/Shared/Chip',
  tags: ['autodocs'],
  args: {
    variant: 'square',
    mode: 'single',
    initialValue: 'inbox',
    showLeadingIcon: true,
    showTrailingIcon: false,
    onChange: fn(),
  },
  argTypes: {
    variant: {
      control: 'inline-radio',
      options: chipVariants,
    },
    mode: {
      control: 'inline-radio',
      options: ['single', 'multi'],
    },
    initialValue: {
      control: 'select',
      options: ['', ...chipItems.map((item) => item.value)],
    },
    showLeadingIcon: {
      control: 'boolean',
    },
    showTrailingIcon: {
      control: 'boolean',
    },
    onChange: {
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
      states: ['unselected', 'selected', 'single', 'multi', 'icon-leading', 'icon-trailing'],
      usedBy: ['agent-studio'],
      interactionNotes: ['Actions log ChipGroup value changes through storybook/test fn spies.'],
      reuseNotes: ['Primitive chip patterns are ready for Agent Studio and filter compositions.'],
    }),
  },
} satisfies Meta<ChipStoryArgs>;

export default meta;

type Story = StoryObj<ChipStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulChipGroup key={`${args.mode}:${args.variant}:${args.initialValue}`} {...args} />,
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: 'VIP' }));
    await expect(args.onChange).toHaveBeenCalledWith(args.mode === 'single' ? 'vip' : expect.arrayContaining(['vip']));
  },
};

export const VariantSet: Story = {
  args: {
    onChange: fn(),
  },
  render: ({ mode, initialValue, showLeadingIcon, showTrailingIcon, onChange }) => (
    <div className="bg-fill-normal-normal flex flex-col gap-4 p-6">
      {chipVariants.map((variant) => (
        <StatefulChipGroup
          key={variant}
          variant={variant}
          mode={mode}
          initialValue={initialValue}
          showLeadingIcon={showLeadingIcon}
          showTrailingIcon={showTrailingIcon}
          onChange={onChange}
        />
      ))}
    </div>
  ),
};
