'use client';

// 문서 탐색 모드 전용 입력 박스. 엔터/보내기 클릭 시 /hybrid-search로 navigate.
// 부모(HomeDocsSection)가 selectedSources를 관리해 tools 쿼리 파라미터로 전달.

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useRouter } from 'next/navigation';

import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconCancel from '@/public/icons/icon/cancel.svg';
import IconFilter from '@/public/icons/icon/filter_small.svg';
import IconSearch from '@/public/icons/icon/search_2.svg';
import { Button } from '@/shared/components/ui/button';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';
import { dateRangeToUrlParams } from '@/shared/utils/temporalRange';

interface DocsQueryBoxProps {
  selectedSources: DocsSource[];
}

export default function DocsQueryBox({ selectedSources }: DocsQueryBoxProps) {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const hasText = value.trim().length > 0;

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    const params = new URLSearchParams({ q: trimmed });
    if (selectedSources.length > 0) {
      params.set('tools', selectedSources.join(','));
    }
    const { start, end } = dateRangeToUrlParams(dateRange);
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    router.push(`/hybrid-search?${params.toString()}`);
  };

  return (
    <div className="shadow-rag-bar border-edge-neutral bg-fill-normal rounded-rounded flex w-190 items-center justify-between border px-4 py-3">
      <div className="flex flex-1 items-center gap-2">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center">
          <IconSearch className="text-icon-alternative h-7 w-7" />
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            // IME 조합 중 Enter (한/중/일 마지막 글자 확정)는 submit 트리거하지 않음.
            if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
          className="text-body-medium text-content-normal placeholder:text-content-assistive flex-1 bg-transparent outline-none"
        />
      </div>
      <div className="flex items-center gap-2.5">
        <DateRangePicker
          value={dateRange}
          onChange={setDateRange}
          align="end"
          trigger={
            <Button
              variant="icon-only-gray"
              size="lg"
              type="button"
              aria-label="기간 필터"
              className={cn(
                'text-icon-normal relative rounded-full',
                dateRange?.from && 'bg-fill-primary-normal-neutral hover:bg-fill-primary-normal-neutral',
              )}
            >
              <IconFilter className="size-6" />
              {dateRange?.from && (
                <span
                  aria-hidden
                  className="bg-fill-primary absolute top-2 right-1.5 size-[5px] rounded-full"
                />
              )}
            </Button>
          }
        />
        {hasText && (
          <Button
            variant="icon-only-gray"
            size="lg"
            type="button"
            onClick={() => setValue('')}
            aria-label="검색어 지우기"
            className="text-icon-normal rounded-full"
          >
            <IconCancel className="size-6" />
          </Button>
        )}
        <span aria-hidden className="bg-edge-normal h-6 w-px shrink-0" />
        <button
          type="button"
          onClick={handleSubmit}
          aria-label="보내기"
          className={`rounded-rounded flex shrink-0 cursor-pointer items-center border border-solid p-2 ${
            hasText ? 'border-fill-primary bg-fill-primary' : 'bg-fill-strong border-edge-assistive'
          }`}
        >
          <IconArrowSend
            className={`h-6 w-6 ${hasText ? 'brightness-0 invert' : 'text-content-assistive'}`}
          />
        </button>
      </div>
    </div>
  );
}
