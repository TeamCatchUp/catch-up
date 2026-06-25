'use client';

// HomeContent의 docs 모드 콘텐츠 — HeroText(docs) + DocsQueryBox + SourceChipsRow + DocsSearchHistorySection.
// selectedSources state를 lifting해 DocsQueryBox(엔터 navigate)와 SourceChipsRow가 공유.

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';

import DocumentSearchFilterRow from '@/shared/components/query/filter/DocumentSearchFilterRow';
import type { DocsSource } from '@/shared/types/source';

import DocsQueryBox from './DocsQueryBox';
import DocsSearchHistorySection from './DocsSearchHistorySection';
import HeroText from './HeroText';

export default function HomeDocsSection() {
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>([]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const [smartFilter, setSmartFilter] = useState(true);

  return (
    <>
      <div className="flex flex-col items-center gap-6 pb-18">
        <div className="grid h-24 place-items-center">
          <HeroText mode="docs" isFocused={false} />
        </div>
        <div className="flex flex-col items-center gap-4">
          <DocsQueryBox selectedSources={selectedSources} dateRange={dateRange} smartFilter={smartFilter} />
          <DocumentSearchFilterRow
            selectedSources={selectedSources}
            onSourcesChange={setSelectedSources}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            smartFilter={smartFilter}
            onSmartFilterChange={setSmartFilter}
          />
        </div>
      </div>
      <DocsSearchHistorySection selectedSources={selectedSources} dateRange={dateRange} smartFilter={smartFilter} />
    </>
  );
}
