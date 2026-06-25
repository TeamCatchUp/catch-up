import type { ReactNode } from 'react';

import {
  ComponentReuseSection,
  DataStateSection,
  DesignTokenSection,
  FigmaMetadataSection,
  LayoutMetadataSection,
} from './FigmaLabMetadataSections';
import type { FigmaLabCase } from './types';

interface FigmaLabChromeProps {
  activeCase: FigmaLabCase | undefined;
  children: ReactNode;
}

export default function FigmaLabChrome({ activeCase, children }: FigmaLabChromeProps) {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-8 py-8">
      <header className="flex flex-col gap-2">
        <p className="text-body-xsmall text-text-normal-assistive font-semibold tracking-wider uppercase">Figma Lab</p>
        <h1 className="text-heading-large text-text-normal-normal font-bold">
          {activeCase?.title ?? '선택된 case가 없습니다'}
        </h1>
        <p className="text-body-medium text-text-normal-alternative">
          Figma 기반 UI 작업을 독립적으로 확인하는 preview surface입니다. 중앙 registry로 case를 추가하고, production
          컴포넌트는 이 route에 의존하지 않게 유지합니다.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="border-line-normal-neutral bg-fill-normal-normal min-w-0 overflow-auto rounded-lg border p-6">
          {children}
        </main>

        <aside className="flex flex-col gap-4">
          <FigmaMetadataSection activeCase={activeCase} />
          <LayoutMetadataSection activeCase={activeCase} />
          <DataStateSection activeCase={activeCase} />
          <ComponentReuseSection activeCase={activeCase} />
          <DesignTokenSection activeCase={activeCase} />
        </aside>
      </div>
    </div>
  );
}
