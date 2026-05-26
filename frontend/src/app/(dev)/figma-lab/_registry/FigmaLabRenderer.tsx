'use client';

import Link from 'next/link';

import {
  FIGMA_LAB_CASES,
  findFigmaLabCase,
  getDefaultFigmaLabCaseId,
} from './cases';
import FigmaLabChrome from './FigmaLabChrome';

interface FigmaLabRendererProps {
  selectedCaseId: string | undefined;
}

export default function FigmaLabRenderer({ selectedCaseId }: FigmaLabRendererProps) {
  const fallbackCaseId = selectedCaseId ?? getDefaultFigmaLabCaseId();
  const activeCase = findFigmaLabCase(fallbackCaseId);

  if (!activeCase) {
    return (
      <FigmaLabChrome activeCase={undefined}>
        <div className="flex min-h-80 flex-col items-center justify-center gap-3 text-center">
          <h2 className="text-heading-medium text-content-normal font-semibold">
            등록된 Figma Lab case가 없습니다
          </h2>
          <p className="text-body-medium text-content-alternative max-w-xl">
            feature-local fixture와 figma-case를 추가한 뒤
            src/app/(dev)/figma-lab/_registry/cases.ts에 등록하세요.
          </p>
        </div>
      </FigmaLabChrome>
    );
  }

  return (
    <FigmaLabChrome activeCase={activeCase}>
      <div className="flex flex-col gap-4">
        {FIGMA_LAB_CASES.length > 1 && (
          <nav className="flex flex-wrap gap-2">
            {FIGMA_LAB_CASES.map((item) => (
              <Link
                key={item.id}
                className="border-edge-neutral bg-fill-strong text-body-small text-content-normal hover:bg-fill-interaction-hover rounded-md border px-3 py-2 transition-colors"
                href={`/figma-lab?case=${item.id}`}
              >
                {item.title}
              </Link>
            ))}
          </nav>
        )}

        <div
          className="border-edge-neutral bg-fill-normal overflow-auto rounded-lg border"
          style={{
            width: activeCase.viewport.width,
            minHeight: activeCase.viewport.height,
          }}
        >
          {activeCase.render()}
        </div>
      </div>
    </FigmaLabChrome>
  );
}
