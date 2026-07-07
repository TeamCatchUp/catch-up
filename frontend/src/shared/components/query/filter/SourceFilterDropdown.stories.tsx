'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import type { DocsSource } from '@/shared/types/source';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SourceFilterDropdown from './SourceFilterDropdown';

type SourcePreset = 'empty' | 'github-slack' | 'all-sources';

interface SourceFilterDropdownStoryArgs {
  preset: SourcePreset;
  preserveInputFocus: boolean;
  defaultOpen: boolean;
  onSourcesChange: (next: DocsSource[]) => void;
  onOpenChange: (open: boolean) => void;
}

const sourcePresetOptions: readonly SourcePreset[] = ['empty', 'github-slack', 'all-sources'];

const sourceFixtures = {
  empty: [],
  'github-slack': ['github', 'slack'],
  'all-sources': ['github', 'channel_talk', 'confluence', 'jira', 'slack'],
} satisfies Record<SourcePreset, DocsSource[]>;

function StatefulSourceFilterDropdown({
  preset,
  preserveInputFocus,
  defaultOpen,
  onSourcesChange,
  onOpenChange,
}: SourceFilterDropdownStoryArgs) {
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>(sourceFixtures[preset]);

  return (
    <div className="bg-fill-normal-normal flex min-h-80 items-start p-6">
      <SourceFilterDropdown
        selectedSources={selectedSources}
        activeMaxWidthClassName="max-w-45"
        preserveInputFocus={preserveInputFocus}
        defaultOpen={defaultOpen}
        onOpenChange={onOpenChange}
        onSourcesChange={(next) => {
          setSelectedSources(next);
          onSourcesChange(next);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Query/SourceFilterDropdown',
  tags: ['autodocs'],
  args: {
    preset: 'empty',
    preserveInputFocus: false,
    defaultOpen: false,
    onSourcesChange: fn(),
    onOpenChange: fn(),
  },
  argTypes: {
    preset: {
      control: 'select',
      options: sourcePresetOptions,
    },
    preserveInputFocus: {
      control: 'boolean',
    },
    defaultOpen: {
      control: 'boolean',
    },
    onSourcesChange: {
      control: false,
    },
    onOpenChange: {
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
      designSource: 'figma',
      states: ['empty', 'selected', 'all-selected', 'search-empty'],
      interactionNotes: ['The play function opens the dropdown and selects Github.'],
      usedBy: ['home-docs', 'hybrid-search'],
    }),
  },
} satisfies Meta<SourceFilterDropdownStoryArgs>;

export default meta;

type Story = StoryObj<SourceFilterDropdownStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulSourceFilterDropdown key={`${args.preset}:${args.defaultOpen}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open source dropdown', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '검색 범위 필터' }));
      await expect(args.onOpenChange).toHaveBeenCalledWith(true);
    });

    await step('select Github', async () => {
      await userEvent.click(await portal.findByRole('button', { name: 'Github' }));
      await expect(args.onSourcesChange).toHaveBeenCalledWith(['github']);
    });
  },
};
