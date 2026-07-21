'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Badge } from './badge';

const badgeVariants = ['default', 'secondary', 'success', 'violet', 'orange', 'pink', 'red'] as const;
const badgeSizes = ['md', 'sm'] as const;

interface BadgeStoryArgs {
  variant: (typeof badgeVariants)[number];
  size: (typeof badgeSizes)[number];
  label: string;
}

const meta = {
  title: 'Primitives/Shared/Badge',
  tags: ['autodocs'],
  args: {
    variant: 'default',
    size: 'md',
    label: '활성',
  },
  argTypes: {
    variant: {
      control: 'select',
      options: badgeVariants,
    },
    size: {
      control: 'inline-radio',
      options: badgeSizes,
    },
    label: {
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
      states: ['default', 'secondary', 'success', 'violet', 'orange', 'pink', 'red', 'sizes'],
      usedBy: ['home-docs'],
      reuseNotes: ['Primitive badge used by mode, status, and classification labels.'],
    }),
  },
} satisfies Meta<BadgeStoryArgs>;

export default meta;

type Story = StoryObj<BadgeStoryArgs>;

export const Playground: Story = {
  render: ({ variant, size, label }) => (
    <div className="bg-fill-normal-normal flex min-h-24 items-center p-6">
      <Badge variant={variant} size={size}>
        {label}
      </Badge>
    </div>
  ),
};

export const VariantSet: Story = {
  render: ({ size }) => (
    <div className="bg-fill-normal-normal flex flex-wrap items-center gap-2 p-6">
      {badgeVariants.map((variant) => (
        <Badge key={variant} variant={variant} size={size}>
          {variant}
        </Badge>
      ))}
    </div>
  ),
};
