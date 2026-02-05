'use client';

import clsx from 'clsx';

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export default function ToggleSwitch({ checked, onChange, disabled = false, className }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={clsx(
        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200',
        checked ? 'bg-blue-50' : 'bg-neutral-3',
        disabled && 'cursor-not-allowed opacity-50',
        !disabled && 'cursor-pointer',
        className,
      )}
    >
      <span
        className={clsx(
          'inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200 ease-out',
          checked ? 'translate-x-5' : 'translate-x-1',
        )}
      />
    </button>
  );
}
