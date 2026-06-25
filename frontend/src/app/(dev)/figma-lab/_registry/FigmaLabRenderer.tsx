'use client';

import Link from 'next/link';

import {
  FIGMA_LAB_CASES,
  getFigmaLabCaseForRoute,
  getFigmaLabCasesByGroup,
  getRelatedFigmaLabCasesByGroup,
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
      <span className="text-body-xsmall text-text-normal-assistive font-semibold">{title}</span>
      <nav className="flex flex-wrap gap-2">
        {cases.map((item) => (
          <Link
            key={item.id}
            className="border-line-normal-neutral bg-fill-normal-strong text-body-small text-text-normal-normal hover:bg-fill-normal-interaction-hover rounded-md border px-3 py-2 transition-colors"
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
  const activeCase = getFigmaLabCaseForRoute({ selectedCaseId, groupId: group?.id });
  const primaryCaseNavTitle = group?.id === 'shared-query-filter' ? 'Shared cases' : 'Feature cases';

  if (!activeCase) {
    return (
      <FigmaLabChrome activeCase={undefined}>
        <div className="flex min-h-80 flex-col items-center justify-center gap-3 text-center">
          <h2 className="text-heading-medium text-text-normal-normal font-semibold">
            등록된 Figma Lab case가 없습니다
          </h2>
          <p className="text-body-medium text-text-normal-alternative max-w-xl">
            feature-local fixture와 figma-case를 추가한 뒤 src/app/(dev)/figma-lab/_registry/cases.ts에 등록하세요.
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
            className="text-body-small text-text-normal-alternative hover:text-text-normal-normal w-fit transition-colors"
            href="/figma-lab"
          >
            ← Feature UI Lab
          </Link>
          {group && (
            <div className="border-line-normal-neutral bg-fill-normal-strong flex flex-col gap-1 rounded-lg border p-4">
              <h2 className="text-heading-small text-text-normal-normal font-semibold">{group.title}</h2>
              <p className="text-body-small text-text-normal-alternative">{group.description}</p>
            </div>
          )}
          <CaseNavSection title={group ? primaryCaseNavTitle : 'All cases'} cases={primaryCases} groupId={group?.id} />
          <CaseNavSection title="Related shared components" cases={relatedCases} groupId={group?.id} />
        </div>

        <div
          className="border-line-normal-neutral bg-fill-normal-normal overflow-auto rounded-lg border"
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
