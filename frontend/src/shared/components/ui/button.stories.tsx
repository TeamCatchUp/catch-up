'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconAdd from '@/public/icons/icon/add.svg';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Button } from './button';

const buttonVariants = [
  'box-solid-primary',
  'box-outline-gray',
  'box-outline-blue',
  'box-soft-primary',
  'capsule-solid-primary',
  'capsule-outline-mono',
  'text-primary-blue',
  'icon-outline-gray',
] as const;

const buttonSizes = ['lg', 'md', 'sm', 'xs'] as const;

interface ButtonStoryArgs {
  variant: (typeof buttonVariants)[number];
  size: (typeof buttonSizes)[number];
  disabled: boolean;
  showIcon: boolean;
  label: string;
  onClick: () => void;
}

const meta = {
  title: 'Primitives/Shared/Button',
  tags: ['autodocs'],
  args: {
    variant: 'box-solid-primary',
    size: 'md',
    disabled: false,
    showIcon: true,
    label: '새로 만들기',
    onClick: fn(),
  },
  argTypes: {
    variant: {
      control: 'select',
      options: buttonVariants,
    },
    size: {
      control: 'inline-radio',
      options: buttonSizes,
    },
    disabled: {
      control: 'boolean',
    },
    showIcon: {
      control: 'boolean',
    },
    label: {
      control: 'text',
    },
    onClick: {
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
      states: ['default', 'disabled', 'icon-leading'],
      interactionNotes: ['Actions log click events through storybook/test fn spies.'],
      reuseNotes: ['Primitive button used by date picker actions, status pages, and feature surfaces.'],
    }),
  },
} satisfies Meta<ButtonStoryArgs>;

export default meta;

type Story = StoryObj<ButtonStoryArgs>;

export const Playground: Story = {
  render: ({ label, showIcon, ...args }) => (
    <div className="bg-fill-normal-normal flex min-h-24 items-center gap-3 p-6">
      <Button {...args}>{showIcon && <IconAdd className="size-5" />}{label}</Button>
    </div>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: args.label }));
    await expect(args.onClick).toHaveBeenCalled();
  },
};

export const VariantSet: Story = {
  args: {
    onClick: fn(),
  },
  render: ({ label, size, showIcon, disabled, onClick }) => (
    <div className="bg-fill-normal-normal flex flex-wrap items-center gap-3 p-6">
      {buttonVariants.slice(0, 6).map((variant) => (
        <Button key={variant} variant={variant} size={size} disabled={disabled} onClick={onClick}>
          {showIcon && <IconAdd className="size-5" />}
          {variant === 'box-solid-primary' ? label : variant}
        </Button>
      ))}
    </div>
  ),
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['variant-set'],
      layoutNotes: ['Shows high-use button variants at one size for visual comparison.'],
    }),
  },
};
