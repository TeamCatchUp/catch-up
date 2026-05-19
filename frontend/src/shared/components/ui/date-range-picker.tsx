'use client';

import { useCallback, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { format, isSameDay, startOfToday } from 'date-fns';
import { ko } from 'date-fns/locale';

import IconCalendar from '@/public/icons/icon/calendar.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconDeleteCircle from '@/public/icons/icon/delete_circle.svg';
import { cn } from '@/shared/utils/cn';

import { Button } from './button';
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
  const [open, setOpen] = useState(false);
  const [tempRange, setTempRange] = useState<DateRange | undefined>(value);

  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (next) setTempRange(value);
      setOpen(next);
    },
    [value],
  );

  const isTodaySelected =
    tempRange?.from &&
    tempRange?.to &&
    isSameDay(tempRange.from, tempRange.to) &&
    isSameDay(tempRange.from, startOfToday());

  const handleSelectToday = useCallback(() => {
    if (isTodaySelected) {
      setTempRange(undefined);
    } else {
      const today = startOfToday();
      setTempRange({ from: today, to: today });
    }
  }, [isTodaySelected]);

  const handleReset = useCallback(() => {
    setTempRange(undefined);
  }, []);

  const handleClear = useCallback(() => {
    onChange?.(undefined);
  }, [onChange]);

  const handleClose = useCallback(() => {
    setOpen(false);
  }, []);

  const handleApply = useCallback(() => {
    onChange?.(tempRange);
    setOpen(false);
  }, [onChange, tempRange]);

  const displayFrom = value?.from ? format(value.from, dateFormat) : undefined;
  const displayTo = value?.to ? format(value.to, dateFormat) : undefined;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        className={cn(
          'border-edge-neutral bg-fill-normal flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-2',
          className,
        )}
      >
        <IconCalendar className="text-icon-neutral size-5" />
        {displayFrom ? (
          <>
            <span className="text-body-small text-content-neutral">{displayFrom}</span>
            <span className="text-body-small text-content-neutral">-</span>
            <span className="text-body-small text-content-neutral">{displayTo ?? displayFrom}</span>
            <IconDeleteCircle
              className="text-icon-assistive size-5"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                handleClear();
              }}
            />
          </>
        ) : (
          <span className="text-body-small text-content-assistive">{placeholder}</span>
        )}
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={4}
        className="shadow-modal flex w-auto flex-col gap-4 rounded-2xl p-5"
      >
        <Calendar
          mode="range"
          selected={tempRange}
          onSelect={setTempRange}
          numberOfMonths={numberOfMonths}
          locale={ko}
          disabled={{ after: startOfToday() }}
          formatters={{ formatCaption: (month) => format(month, 'yyyy.M') }}
        />

        {/* Divider */}
        <div className="border-edge-normal border-t" />

        {/* Action Bar */}
        <div className="flex items-center justify-between">
          {/* 좌측: 오늘 선택 + 초기화 */}
          <div className="flex items-center gap-3">
            <Button
              variant="box-outline-gray"
              size="sm"
              onClick={handleSelectToday}
              className={cn('w-22.5', isTodaySelected && 'border-edge-strong bg-fill-interaction-pressed')}
            >
              {isTodaySelected && <IconCheck className="size-5" />}
              오늘 선택
            </Button>
            <Button variant="text-secondary-mono" size="sm" onClick={handleReset}>
              초기화
            </Button>
          </div>

          {/* 우측: 닫기 + 적용 */}
          <div className="flex items-center gap-3">
            <Button variant="box-outline-gray" size="md" onClick={handleClose} className="w-30">
              닫기
            </Button>
            <Button variant="box-solid-primary" size="md" onClick={handleApply} className="w-30">
              적용
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export { DateRangePicker };
export type { DateRangePickerProps };
