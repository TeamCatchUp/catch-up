'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';

import DocumentSearchFilterRow from '@/shared/components/query/filter/DocumentSearchFilterRow';
import type { DocsSource } from '@/shared/types/source';

import { documentSearchFilterRowFixture } from './documentSearchFilterRow.fixture';

function useFilterFixture(fixture: (typeof documentSearchFilterRowFixture)[keyof typeof documentSearchFilterRowFixture]) {
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>([...fixture.selectedSources]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(fixture.dateRange);
  const [smartFilter, setSmartFilter] = useState(fixture.smartFilter);

  return {
    selectedSources,
    setSelectedSources,
    dateRange,
    setDateRange,
    smartFilter,
    setSmartFilter,
  };
}

export function EntryFilterRowPreview() {
  const defaultRow = useFilterFixture(documentSearchFilterRowFixture.entryDefault);
  const selectedRow = useFilterFixture(documentSearchFilterRowFixture.entrySelected);

  return (
    <div className="bg-fill-normal flex min-h-full flex-col justify-center gap-5 p-6">
      <DocumentSearchFilterRow
        selectedSources={defaultRow.selectedSources}
        onSourcesChange={defaultRow.setSelectedSources}
        dateRange={defaultRow.dateRange}
        onDateRangeChange={defaultRow.setDateRange}
        smartFilter={defaultRow.smartFilter}
        onSmartFilterChange={defaultRow.setSmartFilter}
      />
      <DocumentSearchFilterRow
        selectedSources={selectedRow.selectedSources}
        onSourcesChange={selectedRow.setSelectedSources}
        dateRange={selectedRow.dateRange}
        onDateRangeChange={selectedRow.setDateRange}
        smartFilter={selectedRow.smartFilter}
        onSmartFilterChange={selectedRow.setSmartFilter}
      />
    </div>
  );
}

export function ResultExpandedFilterRowPreview() {
  const row = useFilterFixture(documentSearchFilterRowFixture.resultExpanded);

  return (
    <div className="bg-fill-normal flex min-h-full items-center p-6">
      <div className="w-full" style={{ maxWidth: 900 }}>
        <DocumentSearchFilterRow
          variant="result-expanded"
          selectedSources={row.selectedSources}
          onSourcesChange={row.setSelectedSources}
          dateRange={row.dateRange}
          onDateRangeChange={row.setDateRange}
          smartFilter={row.smartFilter}
          onSmartFilterChange={row.setSmartFilter}
          preserveInputFocus
        />
      </div>
    </div>
  );
}

export function SourceDropdownOpenPreview() {
  const row = useFilterFixture(documentSearchFilterRowFixture.sourceDropdownOpen);

  return (
    <div className="bg-fill-normal flex min-h-full items-start p-6">
      <DocumentSearchFilterRow
        selectedSources={row.selectedSources}
        onSourcesChange={row.setSelectedSources}
        dateRange={row.dateRange}
        onDateRangeChange={row.setDateRange}
        smartFilter={row.smartFilter}
        onSmartFilterChange={row.setSmartFilter}
        initialOpenFilter="source"
      />
    </div>
  );
}

export function DatePickerOpenPreview() {
  const row = useFilterFixture(documentSearchFilterRowFixture.datePickerOpen);

  return (
    <div className="bg-fill-normal flex min-h-full items-start p-6">
      <DocumentSearchFilterRow
        selectedSources={row.selectedSources}
        onSourcesChange={row.setSelectedSources}
        dateRange={row.dateRange}
        onDateRangeChange={row.setDateRange}
        smartFilter={row.smartFilter}
        onSmartFilterChange={row.setSmartFilter}
        initialOpenFilter="date"
      />
    </div>
  );
}
