'use client';

// form 콘텐츠 — form.inputs[] 를 라벨/값 행으로, submitted_at 을 하단에 표시.
// 입력 행이 많으면 Collapsible 로 접어 긴 폼이 패널을 길게 늘이지 않게 한다.

import { useState } from 'react';

import Collapsible from '@/features/hybrid-search/components/original/Collapsible';
import type { OriginalFormInput, OriginalFormPayload } from '@/features/hybrid-search/types/originalApi';
import CheckCircleFilled from '@/public/icons/icon/check_circle_filled.svg';
import ChevronIcon from '@/public/icons/icon/dropdown_down.svg';

interface FormContentProps {
  content: OriginalFormPayload;
}

// 이 개수를 넘으면 입력 행을 접기/펴기로 전환.
const COLLAPSE_THRESHOLD = 3;

// ISO datetime → 'YYYY-MM-DD HH:MM AM/PM'. 파싱 불가하면 원문 그대로.
function formatSubmittedAt(value: string | undefined): string | null {
  const raw = value?.trim();
  if (!raw) return null;

  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  const day = String(parsed.getDate()).padStart(2, '0');
  const hour24 = parsed.getHours();
  const meridiem = hour24 < 12 ? 'AM' : 'PM';
  const hour12 = String(hour24 % 12 || 12).padStart(2, '0');
  const minute = String(parsed.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour12}:${minute} ${meridiem}`;
}

function FormInputRow({ input }: { input: OriginalFormInput }) {
  const label = input.label?.trim() ? input.label : '항목';
  const value = input.value?.trim();

  return (
    <div className="flex flex-col gap-2">
      <span className="text-heading-small text-content-normal">{label}</span>
      <span className="text-body-small text-content-normal break-words">
        {value ?? <span className="text-content-assistive">없음</span>}
      </span>
    </div>
  );
}

export default function FormContent({ content }: FormContentProps) {
  const { inputs } = content.form;
  const isCollapsible = inputs.length > COLLAPSE_THRESHOLD;
  const [open, setOpen] = useState(false);
  const submittedAt = formatSubmittedAt(content.form.submitted_at);

  const rows = (
    <div className="flex flex-col gap-3">
      {inputs.length > 0 ? (
        inputs.map((input, index) => (
          <FormInputRow key={`${input.binding_key ?? input.label ?? 'input'}-${index}`} input={input} />
        ))
      ) : (
        <span className="text-body-small text-content-assistive">제출된 항목이 없어요.</span>
      )}
    </div>
  );

  return (
    <div className="bg-fill-normal border-edge-neutral flex w-full flex-col gap-3 rounded-xl border px-4 py-3">
      {isCollapsible ? (
        <Collapsible
          open={open}
          onOpenChange={setOpen}
          header={
            <div className="flex w-full items-center gap-2">
              <span className="text-heading-small text-content-normal flex-1 text-left">
                제출 항목 {inputs.length}개
              </span>
              <ChevronIcon
                aria-hidden
                className={`text-icon-alternative h-4.5 w-4.5 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
              />
            </div>
          }
        >
          <div className="pt-3">{rows}</div>
        </Collapsible>
      ) : (
        rows
      )}

      {submittedAt && (
        <div className="border-edge-normal flex items-center gap-1.5 border-t pt-3">
          <CheckCircleFilled className="text-accent-green h-5 w-5 shrink-0" />
          <span className="text-body-xsmall text-content-assistive">{submittedAt}</span>
        </div>
      )}
    </div>
  );
}
