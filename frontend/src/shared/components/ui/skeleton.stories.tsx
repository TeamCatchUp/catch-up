'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Skeleton } from './skeleton';

interface SkeletonStoryArgs {
  variant: 'text' | 'card' | 'list';
  rows: number;
}

const meta = {
  title: 'Primitives/Shared/Skeleton',
  tags: ['autodocs'],
  args: {
    variant: 'card',
    rows: 3,
  },
  argTypes: {
    variant: {
      control: 'inline-radio',
      options: ['text', 'card', 'list'],
    },
    rows: {
      control: {
        type: 'number',
        min: 1,
        max: 5,
      },
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['loading', 'text', 'card', 'list'],
      usedBy: ['agent-studio'],
      reuseNotes: ['Primitive loading block used by Agent Studio list skeleton compositions.'],
    }),
  },
} satisfies Meta<SkeletonStoryArgs>;

export default meta;

type Story = StoryObj<SkeletonStoryArgs>;

function SkeletonPreview({ variant, rows }: SkeletonStoryArgs) {
  if (variant === 'text') {
    return (
      <div className="bg-fill-normal-normal flex min-h-32 flex-col gap-2 p-6">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className={index === rows - 1 ? 'h-4 w-48' : 'h-4 w-80'} />
        ))}
      </div>
    );
  }

  if (variant === 'list') {
    return (
      <div className="bg-fill-normal-normal flex min-h-48 flex-col gap-3 p-6">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="border-line-normal-neutral flex items-center gap-3 rounded-lg border p-3">
            <Skeleton className="size-10 rounded-full" />
            <div className="flex flex-1 flex-col gap-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-64" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="bg-fill-normal-normal p-6">
      <div className="border-line-normal-neutral flex w-88 flex-col gap-4 rounded-lg border p-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-20 w-full" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-24" />
        </div>
      </div>
    </div>
  );
}

export const Playground: Story = {
  render: (args) => <SkeletonPreview {...args} />,
};

export const VariantSet: Story = {
  render: ({ rows }) => (
    <div className="bg-fill-normal-normal grid gap-4 p-6">
      <SkeletonPreview variant="text" rows={rows} />
      <SkeletonPreview variant="list" rows={rows} />
      <SkeletonPreview variant="card" rows={rows} />
    </div>
  ),
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['variant-set'],
      layoutNotes: ['Shows text, list, and card loading shapes used by feature skeletons.'],
    }),
  },
};
