'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';

import ResultSearchBar from '@/features/hybrid-search/components/search-bar/ResultSearchBar';
import type { DocsSource } from '@/shared/types/source';

import { type ResultSearchBarFixture, resultSearchBarFixture } from './resultSearchBar.fixture';

function useResultSearchBarFixture(fixture: ResultSearchBarFixture) {
  const [value, setValue] = useState<string>(fixture.value);
  const [chips, setChips] = useState<DocsSource[]>([...fixture.chips]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(fixture.dateRange);
  const [draftSmartFilter, setDraftSmartFilter] = useState<boolean>(fixture.draftSmartFilter);

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

function SearchBarPreviewSurface({
  fixture,
  initialExpanded = false,
}: {
  fixture: ResultSearchBarFixture;
  initialExpanded?: boolean;
}) {
  const state = useResultSearchBarFixture(fixture);

  return (
    <div className="bg-fill-normal flex min-h-full items-start p-6">
      <ResultSearchBar
        value={state.value}
        onValueChange={state.setValue}
        chips={state.chips}
        onChipsChange={state.setChips}
        dateRange={state.dateRange}
        onDateRangeChange={state.setDateRange}
        smartFilter={fixture.smartFilter}
        draftSmartFilter={state.draftSmartFilter}
        onDraftSmartFilterChange={state.setDraftSmartFilter}
        onSubmit={() => undefined}
        onHistorySubmit={state.setValue}
        onClear={() => state.setValue('')}
        onAiModeClick={() => undefined}
        initialExpanded={initialExpanded}
        historyEntries={fixture.historyEntries}
        historyLoading={fixture.historyLoading}
      />
    </div>
  );
}

export function ResultSearchBarCollapsedPreview() {
  return <SearchBarPreviewSurface fixture={resultSearchBarFixture.appliedCollapsed} />;
}

export function ResultSearchBarExpandedPreview() {
  return <SearchBarPreviewSurface fixture={resultSearchBarFixture.expandedDraft} initialExpanded />;
}
