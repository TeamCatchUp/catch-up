'use client';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';

import { isPeriod, type Period,PERIOD_OPTIONS } from '../../../../constants/period';

interface PeriodSelectProps {
  value: Period;
  onChange: (value: Period) => void;
  className?: string;
}

export default function PeriodSelect({ value, onChange, className }: PeriodSelectProps) {
  return (
    <Select
      value={value}
      onValueChange={(next) => {
        if (isPeriod(next)) onChange(next);
      }}
    >
      {/* 채널톡 dropdown spec(gap/6, padding/8) — shared select default(gap-3, py-1.5)보다 좁음 */}
      <SelectTrigger
        className={cn('gap-1.5 py-2', className)}
        endIcon={<IconDropdownDown className="text-icon-neutral size-4 shrink-0" />}
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {PERIOD_OPTIONS.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
