'use client';

// HomeContent의 docs 모드 콘텐츠 — HeroText(docs) + DocsQueryBox + SourceChipsRow + DocsSearchHistorySection.
// selectedSources state를 lifting해 DocsQueryBox(엔터 navigate)와 SourceChipsRow가 공유.

import { useState } from 'react';

import SourceChipsRow from '@/shared/components/SourceChipsRow';
import type { DocsSource } from '@/shared/types/source';

import DocsQueryBox from './DocsQueryBox';
import DocsSearchHistorySection from './DocsSearchHistorySection';
import HeroText from './HeroText';

export default function HomeDocsSection() {
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>([]);

  return (
    <>
      <div className="flex flex-col items-center gap-6 pb-18">
        <div className="grid h-24 place-items-center">
          <HeroText mode="docs" isFocused={false} />
        </div>
        <div className="flex flex-col items-center gap-4">
          <DocsQueryBox selectedSources={selectedSources} />
          <SourceChipsRow
            className="w-222"
            selectedSources={selectedSources}
            onToggle={setSelectedSources}
          />
        </div>
      </div>
      <DocsSearchHistorySection selectedSources={selectedSources} />
    </>
  );
}
