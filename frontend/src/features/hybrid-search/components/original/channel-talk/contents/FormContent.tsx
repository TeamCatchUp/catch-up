'use client';

// form 콘텐츠 — form.inputs[] 를 라벨/값 행으로, submitted_at 을 하단에 표시.
// 접기/펴기 없음 — 디자인은 항상 모든 행을 인라인 노출.

import type { OriginalFormInput, OriginalFormPayload } from '@/features/hybrid-search/types/originalApi';
import { formatSubmittedAt } from '@/features/hybrid-search/utils/format/formatSubmittedAt';
import CheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';

interface FormContentProps {
  content: OriginalFormPayload;
}

function FormInputRow({ input }: { input: OriginalFormInput }) {
  const label = input.label?.trim() ? input.label : '항목';
  const value = input.value?.trim();

  return (
    <div className="flex flex-col gap-2">
      <span className="text-heading-small text-text-normal-normal">{label}</span>
      <span className="text-body-small text-text-normal-normal break-words">
        {value ?? <span className="text-text-normal-assistive">없음</span>}
      </span>
    </div>
  );
}

export default function FormContent({ content }: FormContentProps) {
  const { inputs } = content.form;
  const submittedAt = formatSubmittedAt(content.form.submitted_at);

  return (
    <div className="bg-fill-normal-assistive-dark border-line-normal-normal flex w-full flex-col gap-3 rounded-xl border px-4 py-3">
      <div className="flex flex-col gap-3">
        {inputs.length > 0 ? (
          inputs.map((input, index) => (
            <FormInputRow key={`${input.binding_key ?? input.label ?? 'input'}-${index}`} input={input} />
          ))
        ) : (
          <span className="text-body-small text-text-normal-assistive">제출된 항목이 없어요.</span>
        )}
      </div>

      {submittedAt && (
        <div className="border-line-normal-normal flex items-center gap-1.5 border-t pt-3">
          <CheckCircleFilled className="text-icon-normal-alternative h-5 w-5 shrink-0" />
          <span className="text-body-xsmall text-text-normal-assistive">{submittedAt}</span>
        </div>
      )}
    </div>
  );
}
