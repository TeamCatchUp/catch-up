'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import type { UseRagFiltersReturn } from '@/features/chat/hooks/filter/useRagFilters';
import type { DocsSource } from '@/shared/types/source';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import RagInput from './RagInput';

interface RagInputStoryArgs {
  initialFilterOpen: boolean;
  initialSources: DocsSource[];
  isLoading: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onStop: () => void;
  onNewMessage: () => void;
}

function RagInputSurface(args: RagInputStoryArgs) {
  const [isFilterOpen, setIsFilterOpen] = useState(args.initialFilterOpen);
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>(args.initialSources);
  const filters: UseRagFiltersReturn = {
    isFilterOpen,
    toggleFilter: () => setIsFilterOpen((previous) => !previous),
    selectedSources,
    setSelectedSources,
  };

  return (
    <div className="bg-fill-normal-normal flex min-h-screen items-end justify-center pt-8">
      <div className="w-full">
        <RagInput
          filters={filters}
          isLoading={args.isLoading}
          onSendMessage={args.onSendMessage}
          onStop={args.onStop}
          onNewMessage={args.onNewMessage}
        />
      </div>
    </div>
  );
}

const sourceOptions: readonly DocsSource[] = ['confluence', 'jira', 'slack', 'github', 'channel_talk'];

const meta = {
  title: 'Compositions/Chat/Input/RagInput',
  component: RagInput,
  tags: ['autodocs'],
  args: {
    initialFilterOpen: false,
    initialSources: [],
    isLoading: false,
    onSendMessage: fn(async () => undefined),
    onStop: fn(),
    onNewMessage: fn(),
  },
  argTypes: {
    initialFilterOpen: { control: 'boolean' },
    initialSources: { control: 'check', options: sourceOptions },
    isLoading: { control: 'boolean' },
    onSendMessage: { control: false },
    onStop: { control: false },
    onNewMessage: { control: false },
  },
  parameters: {
    layout: 'fullscreen',
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['empty', 'typing', 'filter-open', 'source-selected', 'loading'],
      usedBy: ['chat'],
      interactionNotes: ['Enter sends a question, source chips update filters, and loading exposes the stop action.'],
    }),
  },
  render: (args) => <RagInputSurface {...args} />,
} satisfies Meta<RagInputStoryArgs>;

export default meta;

type Story = StoryObj<RagInputStoryArgs>;

export const Playground: Story = {};

export const SendWithEnter: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const input = canvas.getByPlaceholderText('답은 이미 사내에 있어요. 바로 찾아드릴게요.');

    await userEvent.type(input, '결제 승인 실패의 재시도 기준을 알려주세요.{enter}');

    await expect(args.onNewMessage).toHaveBeenCalledOnce();
    await waitFor(() => expect(args.onSendMessage).toHaveBeenCalledWith('결제 승인 실패의 재시도 기준을 알려주세요.'));
    await expect(input).toHaveValue('');
  },
};

export const SelectSourceFilter: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const filterToggle = canvas.getByRole('button', { name: '상세 검색' });

    await userEvent.click(filterToggle);
    await expect(filterToggle).toHaveAttribute('aria-expanded', 'true');

    const jiraButton = canvas.getByRole('button', { name: 'Jira' });
    await userEvent.click(jiraButton);
    await expect(jiraButton).toHaveAttribute('aria-pressed', 'true');
  },
};

export const LoadingStop: Story = {
  args: {
    isLoading: true,
    initialFilterOpen: true,
    initialSources: ['jira', 'slack'],
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '답변 생성 중지' }));

    await expect(args.onStop).toHaveBeenCalledOnce();
  },
};
