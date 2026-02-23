'use client';

import { cn } from '@/shared/utils/cn';

interface SegmentedPickerProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
}

export default function SegmentedPicker({ options, value, onChange }: SegmentedPickerProps) {
  return (
    <div className="flex h-9 items-center gap-0.5 rounded-lg border border-neutral-3 bg-neutral-3 p-0.5">
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
                ? 'border border-neutral-5 bg-white text-gray-70 shadow-button'
                : 'text-gray-50 hover:text-gray-60',
            )}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}
