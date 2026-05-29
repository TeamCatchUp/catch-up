'use client';

import Link from 'next/link';

import {
  FIGMA_LAB_CASES,
  findFigmaLabCase,
  getDefaultFigmaLabCaseId,
  getFigmaLabCasesByGroup,
  getRelatedFigmaLabCasesByGroup,
  getVisibleFigmaLabCasesByGroup,
} from './cases';
import FigmaLabChrome from './FigmaLabChrome';
import { findFigmaLabGroup } from './groups';
import type { FigmaLabCase, FigmaLabGroupId } from './types';

interface FigmaLabRendererProps {
  selectedCaseId: string | undefined;
  groupId?: FigmaLabGroupId;
}

interface CaseNavSectionProps {
  title: string;
  cases: readonly FigmaLabCase[];
  groupId?: FigmaLabGroupId;
}

function CaseNavSection({ title, cases, groupId }: CaseNavSectionProps) {
  if (cases.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <span className="text-body-xsmall text-content-assistive font-semibold">{title}</span>
      <nav className="flex flex-wrap gap-2">
        {cases.map((item) => (
          <Link
            key={item.id}
            className="border-edge-neutral bg-fill-strong text-body-small text-content-normal hover:bg-fill-interaction-hover rounded-md border px-3 py-2 transition-colors"
            href={groupId ? `/figma-lab/${groupId}?case=${item.id}` : `/figma-lab/${item.groupId}?case=${item.id}`}
          >
            {item.title}
          </Link>
        ))}
      </nav>
    </div>
  );
}

export default function FigmaLabRenderer({ selectedCaseId, groupId }: FigmaLabRendererProps) {
  const group = findFigmaLabGroup(groupId);
  const primaryCases = group ? getFigmaLabCasesByGroup(group.id) : FIGMA_LAB_CASES;
  const relatedCases = group ? getRelatedFigmaLabCasesByGroup(group.id) : [];
  const visibleCases = group ? getVisibleFigmaLabCasesByGroup(group.id) : FIGMA_LAB_CASES;
  const fallbackCaseId = selectedCaseId ?? getDefaultFigmaLabCaseId(group?.id);
  const activeCase = visibleCases.find((item) => item.id === fallbackCaseId) ?? findFigmaLabCase(fallbackCaseId);
  const primaryCaseNavTitle = group?.id === 'shared-query-filter' ? 'Shared cases' : 'Feature cases';

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
        <div className="flex flex-col gap-4">
          <Link
            className="text-body-small text-content-alternative hover:text-content-normal w-fit transition-colors"
            href="/figma-lab"
          >
            ← Feature UI Lab
          </Link>
          {group && (
            <div className="border-edge-neutral bg-fill-strong flex flex-col gap-1 rounded-lg border p-4">
              <h2 className="text-heading-small text-content-normal font-semibold">{group.title}</h2>
              <p className="text-body-small text-content-alternative">{group.description}</p>
            </div>
          )}
          <CaseNavSection title={group ? primaryCaseNavTitle : 'All cases'} cases={primaryCases} groupId={group?.id} />
          <CaseNavSection title="Related shared components" cases={relatedCases} groupId={group?.id} />
        </div>

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
