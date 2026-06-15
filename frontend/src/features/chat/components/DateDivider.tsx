'use client';

import { cn } from '@/shared/utils/cn';

interface DateDividerProps {
  date: Date;
  formatDate?: (date: Date) => string;
  className?: string;
}

const defaultFormatDate = (date: Date): string => {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${month}.${day}`;
};

export default function DateDivider({ date, formatDate = defaultFormatDate, className }: DateDividerProps) {
  const formattedDate = formatDate(date);

  return (
    <div className={cn('flex items-center justify-center', className)}>
      <div className="border-line-normal-neutral flex-1 border-t" />
      <span className="bg-fill-normal-normal border-line-normal-neutral text-body-xsmall text-text-normal-alternative rounded-full border px-5 py-1">
        {formattedDate}
      </span>
      <div className="border-line-normal-neutral flex-1 border-t" />
    </div>
  );
}
