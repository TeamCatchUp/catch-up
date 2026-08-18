import { Fragment, type ReactNode } from 'react';

import type { OnboardingSummarySection } from '../../types/llmWikiOnboarding';

export interface SummarySectionView extends OnboardingSummarySection {
  /** 행 앞에 전체 폭으로 놓이는 블록 — 수집 설정의 채널 표 */
  lead?: { label: string; content: ReactNode };
}

interface OnboardingSummaryCardProps {
  sections: readonly SummarySectionView[];
}

// 완료 화면의 설정 요약. 값은 행 유형에 따라 텍스트나 배지로 놓인다
export default function OnboardingSummaryCard({ sections }: OnboardingSummaryCardProps) {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-8 rounded-2xl border p-8">
      {sections.map((section, index) => (
        <Fragment key={section.title}>
          {index > 0 && <hr className="border-line-normal-normal" />}
          <section className="flex flex-col gap-8">
            <h3 className="text-heading-medium text-text-normal-normal">{section.title}</h3>

            {section.lead && (
              <div className="flex flex-col gap-4">
                <span className="text-body-small text-text-normal-alternative">{section.lead.label}</span>
                {section.lead.content}
              </div>
            )}

            <dl className="flex flex-col gap-4">
              {section.rows.map((row) => (
                <div key={row.label} className="flex items-start gap-13">
                  <dt className="text-body-small text-text-normal-alternative w-20 shrink-0 pt-1">{row.label}</dt>
                  <dd className="flex min-w-0 flex-wrap items-center gap-3">
                    {row.values.map((value) =>
                      row.variant === 'badge' ? (
                        <span
                          key={value}
                          className="bg-fill-normal-strong text-body-small text-text-normal-normal rounded-lg px-2 py-1"
                        >
                          {value}
                        </span>
                      ) : (
                        <span key={value} className="text-body-small text-text-normal-normal pt-1">
                          {value}
                        </span>
                      ),
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        </Fragment>
      ))}
    </div>
  );
}
