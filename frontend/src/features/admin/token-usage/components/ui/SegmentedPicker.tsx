'use client';

import { cn } from '@/shared/utils/cn';

interface SegmentedPickerProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

export default function SegmentedPicker({ options, value, onChange }: SegmentedPickerProps) {
  return (
    <div className="border-edge-neutral bg-fill-interaction-pressed flex h-9 items-center gap-0.5 rounded-lg border p-0.5">
      {options.map((option) => {
        const isSelected = option === value;
        return (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={cn(
              'text-body-small cursor-pointer rounded-[7px] px-3 py-1 transition-colors',
              isSelected
                ? 'border-edge-strong text-content-neutral shadow-button border bg-fill-normal'
                : 'hover:text-content-alternative text-content-alternative',
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}
