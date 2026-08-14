import { Fragment } from 'react';

import type { OnboardingSummarySection } from '../../types/llmWikiOnboarding';

interface OnboardingSummaryCardProps {
  sections: readonly OnboardingSummarySection[];
}

// 완료 화면의 설정 요약. 문서 종류·채널처럼 값이 여러 개인 행이 있어 값을 나란히 놓는다
export default function OnboardingSummaryCard({ sections }: OnboardingSummaryCardProps) {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-8 rounded-2xl border p-8">
      {sections.map((section, index) => (
        <Fragment key={section.title}>
          {index > 0 && <hr className="border-line-normal-normal" />}
          <section className="flex flex-col gap-6">
            <h3 className="text-heading-medium text-text-normal-normal">{section.title}</h3>
            <dl className="flex flex-col gap-4">
              {section.rows.map((row) => (
                <div key={row.label} className="flex items-start gap-8">
                  <dt className="text-body-small text-text-normal-alternative w-20 shrink-0">{row.label}</dt>
                  <dd className="text-body-small text-text-normal-normal flex min-w-0 flex-wrap gap-8">
                    {row.values.map((value) => (
                      <span key={value}>{value}</span>
                    ))}
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
