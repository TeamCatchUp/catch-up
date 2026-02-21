'use client';

import type { DateRange } from 'react-day-picker';
import { format } from 'date-fns';
import { ko } from 'date-fns/locale';

import IconCalendar from '@/public/icons/icon/calendar.svg';
import { cn } from '@/shared/utils/cn';

import { Calendar } from './calendar';
import { Popover, PopoverContent, PopoverTrigger } from './popover';

interface DateRangePickerProps {
  /** 선택된 날짜 범위 */
  value?: DateRange;
  /** 날짜 범위 변경 콜백 */
  onChange?: (range: DateRange | undefined) => void;
  /** Trigger 버튼 className */
  className?: string;
  /** 날짜 포맷 (기본: yyyy.MM.dd) */
  dateFormat?: string;
  /** 플레이스홀더 */
  placeholder?: string;
  /** 표시할 월 수 (기본: 2) */
  numberOfMonths?: number;
}

function DateRangePicker({
  value,
  onChange,
  className,
  dateFormat = 'yyyy.MM.dd',
  placeholder = '날짜를 선택하세요',
  numberOfMonths = 2,
}: DateRangePickerProps) {
  const displayFrom = value?.from ? format(value.from, dateFormat) : undefined;
  const displayTo = value?.to ? format(value.to, dateFormat) : undefined;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'border-neutral-3 flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border bg-white px-2.5 py-2',
            className,
          )}
        >
          <IconCalendar className="size-6 text-gray-50" />
          {displayFrom ? (
            <>
              <span className="text-body-small text-gray-70">{displayFrom}</span>
              <span className="text-body-small text-gray-70">-</span>
              <span className="text-body-small text-gray-70">{displayTo ?? displayFrom}</span>
            </>
          ) : (
            <span className="text-body-small text-gray-30">{placeholder}</span>
          )}
        </button>
      </PopoverTrigger>

      <PopoverContent align="start" sideOffset={4} className="shadow-modal w-auto rounded-2xl p-0">
        <Calendar mode="range" selected={value} onSelect={onChange} numberOfMonths={numberOfMonths} locale={ko} />
      </PopoverContent>
    </Popover>
  );
}

export { DateRangePicker };
export type { DateRangePickerProps };
