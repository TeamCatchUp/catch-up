'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import type { DocsSource } from '@/shared/types/source';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import DocumentSearchFilterRow from './DocumentSearchFilterRow';

type SourcePreset = 'empty' | 'github-slack' | 'all-sources';
type DatePreset = 'none' | 'april-range' | 'single-day';

interface DocumentSearchFilterRowFixture {
  selectedSources: DocsSource[];
  dateRange: DateRange | undefined;
  smartFilter: boolean;
}

interface DocumentSearchFilterRowStoryArgs {
  sourcePreset: SourcePreset;
  datePreset: DatePreset;
  smartFilter: boolean;
  variant: 'entry' | 'result-expanded';
  showComparisonRow: boolean;
  preserveInputFocus: boolean;
  onSourcesChange: (next: DocsSource[]) => void;
  onDateRangeChange: (next: DateRange | undefined) => void;
  onSmartFilterChange: (next: boolean) => void;
  onFilterOverlayOpenChange: (open: boolean) => void;
}

const sourcePresetOptions: readonly SourcePreset[] = ['empty', 'github-slack', 'all-sources'];
const datePresetOptions: readonly DatePreset[] = ['none', 'april-range', 'single-day'];

const documentSearchFilterRowFixture = {
  entryDefault: {
    selectedSources: [],
    dateRange: undefined,
    smartFilter: true,
  },
  entrySelected: {
    selectedSources: ['github', 'slack'] satisfies DocsSource[],
    dateRange: {
      from: new Date(2026, 3, 7),
      to: new Date(2026, 3, 20),
    },
    smartFilter: true,
  },
  entryAllSources: {
    selectedSources: ['github', 'channel_talk', 'confluence', 'jira', 'slack'] satisfies DocsSource[],
    dateRange: {
      from: new Date(2026, 4, 11),
      to: new Date(2026, 4, 11),
    },
    smartFilter: false,
  },
} satisfies Record<string, DocumentSearchFilterRowFixture>;

function getFixtureFromArgs(args: DocumentSearchFilterRowStoryArgs): DocumentSearchFilterRowFixture {
  const selectedSources =
    args.sourcePreset === 'all-sources'
      ? documentSearchFilterRowFixture.entryAllSources.selectedSources
      : args.sourcePreset === 'github-slack'
        ? documentSearchFilterRowFixture.entrySelected.selectedSources
        : documentSearchFilterRowFixture.entryDefault.selectedSources;
  const dateRange =
    args.datePreset === 'single-day'
      ? documentSearchFilterRowFixture.entryAllSources.dateRange
      : args.datePreset === 'april-range'
        ? documentSearchFilterRowFixture.entrySelected.dateRange
        : documentSearchFilterRowFixture.entryDefault.dateRange;

  return {
    selectedSources,
    dateRange,
    smartFilter: args.smartFilter,
  };
}

function useFilterFixture(
  fixture: DocumentSearchFilterRowFixture,
  actions?: Pick<
    DocumentSearchFilterRowStoryArgs,
    'onSourcesChange' | 'onDateRangeChange' | 'onSmartFilterChange' | 'onFilterOverlayOpenChange'
  >,
) {
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>([...fixture.selectedSources]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(fixture.dateRange);
  const [smartFilter, setSmartFilter] = useState(fixture.smartFilter);

  return {
    selectedSources,
    setSelectedSources: (next: DocsSource[]) => {
      setSelectedSources(next);
      actions?.onSourcesChange(next);
    },
    dateRange,
    setDateRange: (next: DateRange | undefined) => {
      setDateRange(next);
      actions?.onDateRangeChange(next);
    },
    smartFilter,
    setSmartFilter: (next: boolean) => {
      setSmartFilter(next);
      actions?.onSmartFilterChange(next);
    },
    setFilterOverlayOpen: (open: boolean) => {
      actions?.onFilterOverlayOpenChange(open);
    },
  };
}

function StatefulFilterRow({
  fixture,
  actions,
  variant,
  preserveInputFocus,
}: {
  fixture: DocumentSearchFilterRowFixture;
  actions?: Pick<
    DocumentSearchFilterRowStoryArgs,
    'onSourcesChange' | 'onDateRangeChange' | 'onSmartFilterChange' | 'onFilterOverlayOpenChange'
  >;
  variant?: 'entry' | 'result-expanded';
  preserveInputFocus?: boolean;
}) {
  const row = useFilterFixture(fixture, actions);
  return (
    <DocumentSearchFilterRow
      variant={variant}
      selectedSources={row.selectedSources}
      onSourcesChange={row.setSelectedSources}
      dateRange={row.dateRange}
      onDateRangeChange={row.setDateRange}
      smartFilter={row.smartFilter}
      onSmartFilterChange={row.setSmartFilter}
      preserveInputFocus={preserveInputFocus}
      onFilterOverlayOpenChange={row.setFilterOverlayOpen}
    />
  );
}

function EntryFilterRowCanvas(args: DocumentSearchFilterRowStoryArgs) {
  const primaryFixture = getFixtureFromArgs(args);
  const primaryResetKey = `${args.sourcePreset}:${args.datePreset}:${args.smartFilter}`;
  const width = args.variant === 'result-expanded' ? 920 : 780;

  return (
    <div
      className="bg-fill-normal-normal flex flex-col justify-center gap-5 p-6"
      style={{ minHeight: args.showComparisonRow ? 180 : 96, width }}
    >
      <StatefulFilterRow
        key={primaryResetKey}
        fixture={primaryFixture}
        actions={args}
        variant={args.variant}
        preserveInputFocus={args.preserveInputFocus}
      />
      {args.showComparisonRow && (
        <StatefulFilterRow key="comparison-row" fixture={documentSearchFilterRowFixture.entrySelected} />
      )}
    </div>
  );
}

const meta = {
  title: 'Compositions/Shared/Query/DocumentSearchFilterRow',
  args: {
    sourcePreset: 'empty',
    datePreset: 'none',
    smartFilter: true,
    variant: 'entry',
    showComparisonRow: true,
    preserveInputFocus: false,
    onSourcesChange: fn(),
    onDateRangeChange: fn(),
    onSmartFilterChange: fn(),
    onFilterOverlayOpenChange: fn(),
  },
  argTypes: {
    sourcePreset: {
      control: 'select',
      options: sourcePresetOptions,
    },
    datePreset: {
      control: 'select',
      options: datePresetOptions,
    },
    smartFilter: {
      control: 'boolean',
    },
    variant: {
      control: 'inline-radio',
      options: ['entry', 'result-expanded'],
    },
    showComparisonRow: {
      control: 'boolean',
    },
    preserveInputFocus: {
      control: 'boolean',
    },
    onSourcesChange: {
      control: false,
    },
    onDateRangeChange: {
      control: false,
    },
    onSmartFilterChange: {
      control: false,
    },
    onFilterOverlayOpenChange: {
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
      figmaLab: {
        caseId: 'document-search-filter-row-entry',
        groupId: 'shared-query-filter',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-62155&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14308:62155',
      },
      viewport: {
        width: 780,
        height: 180,
      },
      states: ['default', 'selected'],
      usedBy: ['home-docs', 'hybrid-search'],
      dataNotes: [
        'default: empty source/date filters with smart filter on',
        'selected: github/slack and 2026-04-07 through 2026-04-20 selected',
      ],
      reuseNotes: [
        'Reuses SourceFilterDropdown for source chip, search input, and icon assets.',
        'Reuses DateFilterChip and DateRangePicker trigger behavior.',
        'Reuses SmartFilterControl with tooltip, switch, and info icon composition.',
      ],
      interactionNotes: [
        'Controls expose source/date presets, variant, comparison row visibility, and smart filter state.',
        'Actions log source/date/smart-filter changes and filter overlay open changes through storybook/test fn spies.',
        'The Entry play function opens the source dropdown, selects Github, opens the date picker, and toggles smart filter.',
      ],
      tokenNotes: [
        'Figma gap/20 maps to gap-5.',
        'Figma gap/10 maps to gap-2.5.',
        'Figma Fill/Primary/Normal/Neutral maps to bg-fill-primary-normal-neutral.',
      ],
    }),
  },
} satisfies Meta<DocumentSearchFilterRowStoryArgs>;

export default meta;

type Story = StoryObj<DocumentSearchFilterRowStoryArgs>;

export const Entry: Story = {
  name: 'Entry',
  render: (args) => <EntryFilterRowCanvas {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await step('open source dropdown and select Github', async () => {
      await userEvent.click(canvas.getAllByRole('button', { name: '검색 범위 필터' })[0]);
      await expect(args.onFilterOverlayOpenChange).toHaveBeenCalledWith(true);
      await userEvent.click(await portal.findByRole('button', { name: 'Github' }));
      await expect(args.onSourcesChange).toHaveBeenCalledWith(['github']);
    });

    await step('open date picker', async () => {
      await userEvent.click(canvas.getAllByRole('button', { name: '날짜 필터' })[0]);
      await expect(args.onFilterOverlayOpenChange).toHaveBeenCalledWith(true);
      await expect(await portal.findByRole('button', { name: '오늘 선택' })).toBeInTheDocument();
    });

    await step('toggle smart filter', async () => {
      await userEvent.click(canvas.getAllByRole('switch', { name: '스마트 필터' })[0]);
      await expect(args.onSmartFilterChange).toHaveBeenCalledWith(false);
    });
  },
};
