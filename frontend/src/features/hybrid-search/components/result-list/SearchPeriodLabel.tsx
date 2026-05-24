'use client';

// 기간 검색 결과 라벨. 결과 목록 최상단에 표시.
// 기간이 설정된 경우에만 ResultListSection이 렌더한다.

import type { DateRange } from 'react-day-picker';
import { format } from 'date-fns';

import IconCalendarFilled from '@/public/icons/icon/calendar_filled.svg';

interface SearchPeriodLabelProps {
  dateRange: DateRange;
}

export default function SearchPeriodLabel({ dateRange }: SearchPeriodLabelProps) {
  if (!dateRange.from) return null;

  const from = format(dateRange.from, 'yyyy.MM.dd');
  const to = dateRange.to ? format(dateRange.to, 'yyyy.MM.dd') : from;

  return (
    <div className="flex items-center gap-2">
      <IconCalendarFilled className="text-icon-neutral size-4.5 shrink-0" />
      <span className="text-body-xsmall text-content-neutral">{`${from} ~ ${to}`}</span>
    </div>
  );
}
