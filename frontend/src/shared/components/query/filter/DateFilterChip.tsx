import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { format } from 'date-fns';

import IconCalendar from '@/public/icons/icon/calendar.svg';
import { cn } from '@/shared/utils/cn';

import { DateRangePicker } from '../../ui/date-range-picker';
import FilterTriggerButton from './FilterTriggerButton';

interface DateFilterChipProps {
  value: DateRange | undefined;
  onChange: (next: DateRange | undefined) => void;
  activeMaxWidthClassName: string;
  preserveInputFocus?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}

function formatDateRangeLabel(range: DateRange | undefined): string | undefined {
  if (!range?.from) return undefined;
  const from = format(range.from, 'yyyy년 M월 d일');
  const to = format(range.to ?? range.from, 'yyyy년 M월 d일');
  return from === to ? from : `${from} - ${to}`;
}

export default function DateFilterChip({
  value,
  onChange,
  activeMaxWidthClassName,
  preserveInputFocus,
  defaultOpen = false,
  onOpenChange,
}: DateFilterChipProps) {
  const [open, setOpen] = useState(defaultOpen);
  const valueLabel = formatDateRangeLabel(value);
  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <DateRangePicker
      value={value}
      onChange={onChange}
      align="start"
      defaultOpen={defaultOpen}
      onOpenChange={handleOpenChange}
      contentProps={{ 'data-document-search-filter-popover': true }}
      trigger={
        <FilterTriggerButton
          active={Boolean(valueLabel)}
          label="날짜"
          valueLabel={valueLabel}
          open={open}
          Icon={IconCalendar}
          aria-label="날짜 필터"
          className={cn(valueLabel && activeMaxWidthClassName)}
          onMouseDown={preserveInputFocus ? (event) => event.preventDefault() : undefined}
        />
      }
    />
  );
}
