'use client';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { cn } from '@/shared/utils/cn';

import { isPeriod, type Period, PERIOD_OPTIONS } from '../../../constants/period';

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
      {/*
       * 채널톡 dropdown spec(gap/6, padding/8) — shared select default(gap-3, px-2.5, py-1.5)보다 좁음.
       *
       * `w-auto`와 `[&>span]:line-clamp-none`이 한 쌍이다. shared SelectTrigger는 `w-full`에
       * `[&>span]:line-clamp-1`이 걸려 있어서, 호출부가 고정 폭을 주면 라벨이 말없이 잘린다.
       * 실제로 그랬다 — 68px 트리거에서 border 2 + px 20 + gap 6 + 아이콘 16을 빼면 글자 자리가
       * 24px인데 "1개월"은 15px 폰트로 약 38px다. 폭만 늘리고 line-clamp를 두면 라벨이 길어지는
       * 순간 같은 일이 반복되므로 둘 다 푼다. 폭 하한은 호출부가 min-w-*로 준다.
       */}
      <SelectTrigger
        className={cn('w-auto gap-1.5 px-2 py-2 [&>span]:line-clamp-none', className)}
        endIcon={<IconDropdownDown className="text-icon-normal-neutral size-4 shrink-0" />}
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
