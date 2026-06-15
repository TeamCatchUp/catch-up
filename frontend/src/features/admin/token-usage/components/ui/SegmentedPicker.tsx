'use client';

import { cn } from '@/shared/utils/cn';

interface SegmentedPickerProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

export default function SegmentedPicker({ options, value, onChange }: SegmentedPickerProps) {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-strong flex items-center rounded-lg border p-0.5">
      {options.map((option) => {
        const isSelected = option === value;
        return (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={cn(
              'text-body-small h-9 w-19 cursor-pointer rounded-[7px] p-2 text-center transition-colors',
              isSelected
                ? 'border-line-normal-assistive bg-fill-normal-normal text-text-normal-neutral shadow-button border'
                : 'text-text-normal-alternative',
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}
