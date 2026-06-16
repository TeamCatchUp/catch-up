'use client';

import Link from 'next/link';

import { FIGMA_LAB_CASES, getFigmaLabCasesByGroup, getRelatedFigmaLabCasesByGroup } from './cases';
import { FIGMA_LAB_GROUPS } from './groups';

export default function FigmaLabGroupIndex() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-8 py-8">
      <header className="flex flex-col gap-2">
        <p className="text-body-xsmall text-text-normal-assistive font-semibold tracking-wider uppercase">Figma Lab</p>
        <h1 className="text-heading-large text-text-normal-normal font-bold">Feature UI Lab</h1>
        <p className="text-body-medium text-text-normal-alternative">
          Feature 단위로 page assembly와 관련 shared component를 함께 확인하는 dev preview surface입니다.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {FIGMA_LAB_GROUPS.map((group) => {
          const primaryCaseCount = getFigmaLabCasesByGroup(group.id).length;
          const relatedCaseCount = getRelatedFigmaLabCasesByGroup(group.id).length;

          return (
            <Link
              key={group.id}
              href={`/figma-lab/${group.id}`}
              className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover flex min-h-44 flex-col justify-between gap-6 rounded-lg border p-5 transition-colors"
            >
              <div className="flex flex-col gap-2">
                <h2 className="text-heading-small text-text-normal-normal font-semibold">{group.title}</h2>
                <p className="text-body-small text-text-normal-alternative">{group.description}</p>
              </div>
              <div className="text-body-small text-text-normal-assistive flex items-center gap-2">
                <span>{primaryCaseCount} cases</span>
                {relatedCaseCount > 0 && (
                  <>
                    <span aria-hidden>·</span>
                    <span>{relatedCaseCount} related shared</span>
                  </>
                )}
              </div>
            </Link>
          );
        })}
      </div>

      {FIGMA_LAB_CASES.length === 0 && (
        <div className="border-line-normal-neutral bg-fill-normal-strong flex min-h-48 items-center justify-center rounded-lg border">
          <p className="text-body-medium text-text-normal-alternative">등록된 Figma Lab case가 없습니다.</p>
        </div>
      )}
    </div>
  );
}
