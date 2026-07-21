'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import Pagination from './pagination';

interface PaginationStoryArgs {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function StatefulPagination({ currentPage, totalPages, onPageChange }: PaginationStoryArgs) {
  const [page, setPage] = useState(currentPage);

  return (
    <div className="bg-fill-normal-normal flex min-h-24 items-center justify-center p-6">
      <Pagination
        currentPage={page}
        totalPages={totalPages}
        onPageChange={(next) => {
          setPage(next);
          onPageChange(next);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Primitives/Shared/Pagination',
  tags: ['autodocs'],
  args: {
    currentPage: 1,
    totalPages: 13,
    onPageChange: fn(),
  },
  argTypes: {
    currentPage: {
      control: {
        type: 'number',
        min: 1,
        max: 20,
      },
    },
    totalPages: {
      control: {
        type: 'number',
        min: 1,
        max: 50,
      },
    },
    onPageChange: {
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
      states: ['first-group', 'middle-group', 'last-group'],
      usedBy: ['agent-studio'],
      interactionNotes: ['The play function moves to page 2 and checks the callback payload.'],
      reuseNotes: ['Primitive pagination used by table and list surfaces.'],
    }),
  },
} satisfies Meta<PaginationStoryArgs>;

export default meta;

type Story = StoryObj<PaginationStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulPagination key={`${args.currentPage}:${args.totalPages}`} {...args} />,
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '2' }));
    await expect(args.onPageChange).toHaveBeenCalledWith(2);
  },
};

export const PageGroups: Story = {
  args: {
    onPageChange: fn(),
  },
  render: ({ totalPages, onPageChange }) => (
    <div className="bg-fill-normal-normal flex flex-col items-start gap-5 p-6">
      <StatefulPagination currentPage={1} totalPages={totalPages} onPageChange={onPageChange} />
      <StatefulPagination currentPage={6} totalPages={totalPages} onPageChange={onPageChange} />
      <StatefulPagination currentPage={11} totalPages={totalPages} onPageChange={onPageChange} />
    </div>
  ),
};
