import { useMemo } from 'react';
import type { DateRange } from 'react-day-picker';
import { isWithinInterval, parseISO } from 'date-fns';

export default function useFilteredByDateRange<T extends { date: string }>(
  data: T[] | undefined,
  dateRange: DateRange | undefined,
): T[] {
  return useMemo(() => {
    if (!data) return [];
    if (!dateRange?.from) return data;
    const from = dateRange.from;
    const to = dateRange.to ?? dateRange.from;
    return data.filter((d) => isWithinInterval(parseISO(d.date), { start: from, end: to }));
  }, [data, dateRange]);
}
