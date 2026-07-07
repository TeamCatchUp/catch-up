'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { DocsSource } from '@/shared/types/source';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ResultSearchBar from './ResultSearchBar';

type ResultSearchBarPreset = 'applied-collapsed' | 'expanded-draft';

interface ResultSearchBarFixture {
  value: string;
  chips: DocsSource[];
  dateRange: DateRange | undefined;
  smartFilter: boolean;
  draftSmartFilter: boolean;
  historyEntries?: SearchHistoryEntry[];
  historyLoading?: boolean;
}

interface ResultSearchBarStoryArgs {
  preset: ResultSearchBarPreset;
  initialExpanded: boolean;
  historyLoading: boolean;
  onValueChange: (value: string) => void;
  onChipsChange: (next: DocsSource[]) => void;
  onDateRangeChange: (next: DateRange | undefined) => void;
  onDraftSmartFilterChange: (next: boolean) => void;
  onSubmit: () => void;
  onHistorySubmit: (query: string) => void;
  onClear: () => void;
  onAiModeClick: () => void;
}

const presetOptions: readonly ResultSearchBarPreset[] = ['applied-collapsed', 'expanded-draft'];

const resultSearchBarFixtures: Record<ResultSearchBarPreset, ResultSearchBarFixture> = {
  'applied-collapsed': {
    value: '지난주 결제 문서',
    chips: ['github', 'jira'] satisfies DocsSource[],
    dateRange: undefined,
    smartFilter: true,
    draftSmartFilter: true,
  },
  'expanded-draft': {
    value: '이번 주 컨플루언스 문서',
    chips: ['confluence'] satisfies DocsSource[],
    dateRange: {
      from: new Date(2026, 3, 7),
      to: new Date(2026, 3, 20),
    },
    smartFilter: true,
    draftSmartFilter: true,
    historyEntries: [
      {
        id: 'storybook-history-1',
        query: '이번 주 컨플루언스 문서',
        createdAt: new Date(2026, 4, 29, 9, 0, 0),
      },
      {
        id: 'storybook-history-2',
        query: '지난주 결제 승인 슬랙',
        createdAt: new Date(2026, 4, 28, 14, 30, 0),
      },
    ],
    historyLoading: false,
  },
};

function useResultSearchBarFixture(fixture: ResultSearchBarFixture) {
  const [value, setValue] = useState(fixture.value);
  const [chips, setChips] = useState<DocsSource[]>([...fixture.chips]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(fixture.dateRange);
  const [draftSmartFilter, setDraftSmartFilter] = useState(fixture.draftSmartFilter);

  return {
    value,
    setValue,
    chips,
    setChips,
    dateRange,
    setDateRange,
    draftSmartFilter,
    setDraftSmartFilter,
  };
}

function StatefulResultSearchBar(args: ResultSearchBarStoryArgs) {
  const fixture = resultSearchBarFixtures[args.preset];
  const state = useResultSearchBarFixture(fixture);
  const historyLoading = args.historyLoading || fixture.historyLoading;

  return (
    <div className="bg-fill-normal-normal flex min-h-180 items-start p-6">
      <ResultSearchBar
        value={state.value}
        onValueChange={(next) => {
          state.setValue(next);
          args.onValueChange(next);
        }}
        chips={state.chips}
        onChipsChange={(next) => {
          state.setChips(next);
          args.onChipsChange(next);
        }}
        dateRange={state.dateRange}
        onDateRangeChange={(next) => {
          state.setDateRange(next);
          args.onDateRangeChange(next);
        }}
        smartFilter={fixture.smartFilter}
        draftSmartFilter={state.draftSmartFilter}
        onDraftSmartFilterChange={(next) => {
          state.setDraftSmartFilter(next);
          args.onDraftSmartFilterChange(next);
        }}
        onSubmit={args.onSubmit}
        onHistorySubmit={(query) => {
          state.setValue(query);
          args.onHistorySubmit(query);
        }}
        onClear={() => {
          state.setValue('');
          args.onClear();
        }}
        onAiModeClick={args.onAiModeClick}
        initialExpanded={args.initialExpanded}
        historyEntries={fixture.historyEntries}
        historyLoading={historyLoading}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Hybrid Search/Search/ResultSearchBar',
  tags: ['autodocs'],
  args: {
    preset: 'applied-collapsed',
    initialExpanded: false,
    historyLoading: false,
    onValueChange: fn(),
    onChipsChange: fn(),
    onDateRangeChange: fn(),
    onDraftSmartFilterChange: fn(),
    onSubmit: fn(),
    onHistorySubmit: fn(),
    onClear: fn(),
    onAiModeClick: fn(),
  },
  argTypes: {
    preset: {
      control: 'select',
      options: presetOptions,
    },
    initialExpanded: {
      control: 'boolean',
    },
    historyLoading: {
      control: 'boolean',
    },
    onValueChange: { control: false },
    onChipsChange: { control: false },
    onDateRangeChange: { control: false },
    onDraftSmartFilterChange: { control: false },
    onSubmit: { control: false },
    onHistorySubmit: { control: false },
    onClear: { control: false },
    onAiModeClick: { control: false },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['collapsed-applied', 'expanded-draft'],
      reuseNotes: [
        'Expanded state reuses shared DocumentSearchFilterRow.',
        'Result status pill reuses shared SmartFilterStatusPill.',
        'History list uses fixture data, so Storybook does not need a search-history query.',
      ],
      interactionNotes: [
        'Actions log text, filter, smart-filter, submit, history, clear, and AI-mode events.',
      ],
    }),
  },
} satisfies Meta<ResultSearchBarStoryArgs>;

export default meta;

type Story = StoryObj<ResultSearchBarStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulResultSearchBar key={`${args.preset}:${args.initialExpanded}`} {...args} />,
};

export const CollapsedApplied: Story = {
  args: {
    preset: 'applied-collapsed',
    initialExpanded: false,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'result-search-bar-collapsed',
        groupId: 'hybrid-search',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-63671&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14308:63671',
      },
      viewport: {
        width: 1240,
        height: 160,
      },
      states: ['collapsed-applied'],
    }),
  },
  render: (args) => <StatefulResultSearchBar key="collapsed-applied" {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('clear search keyword', async () => {
      await expect(canvas.getByDisplayValue('지난주 결제 문서')).toBeInTheDocument();
      await userEvent.click(canvas.getByRole('button', { name: '검색어 지우기' }));
      await expect(args.onClear).toHaveBeenCalled();
    });
  },
};

export const ExpandedDraft: Story = {
  args: {
    preset: 'expanded-draft',
    initialExpanded: true,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'result-search-bar-expanded',
        groupId: 'hybrid-search',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-61606&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14308:61606',
      },
      viewport: {
        width: 1240,
        height: 760,
      },
      states: ['expanded-draft'],
    }),
  },
  render: (args) => <StatefulResultSearchBar key="expanded-draft" {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('submit history item', async () => {
      await expect(canvas.getByDisplayValue('이번 주 컨플루언스 문서')).toBeInTheDocument();
      await userEvent.click(canvas.getByRole('button', { name: /지난주 결제 승인 슬랙/ }));
      await expect(args.onHistorySubmit).toHaveBeenCalledWith('지난주 결제 승인 슬랙');
    });
  },
};
