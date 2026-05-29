import type { ButtonHTMLAttributes, FC, SVGProps } from 'react';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconDropdownUp from '@/public/icons/icon/dropdown_up.svg';
import { cn } from '@/shared/utils/cn';

interface FilterTriggerButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active: boolean;
  label: string;
  valueLabel?: string;
  open?: boolean;
  Icon: FC<SVGProps<SVGSVGElement>>;
}

export default function FilterTriggerButton({
  active,
  label,
  valueLabel,
  open,
  Icon,
  className,
  onMouseDown,
  ...props
}: FilterTriggerButtonProps) {
  const DropdownIcon = open ? IconDropdownUp : IconDropdownDown;

  return (
    <button
      type="button"
      onMouseDown={onMouseDown}
      className={cn(
        'flex h-9 min-w-0 cursor-pointer items-center justify-center gap-2 rounded-lg border px-2.5 py-1.5 transition-colors',
        active
          ? 'border-edge-primary bg-fill-primary-assistive text-content-primary'
          : 'border-edge-neutral bg-fill-normal text-content-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed',
        className,
      )}
      {...props}
    >
      <Icon className={cn('size-5 shrink-0', active ? 'text-icon-primary' : 'text-icon-normal')} />
      {active ? (
        <>
          <span className="text-body-small shrink-0 font-medium whitespace-nowrap">{label}:</span>
          <span className="text-body-small min-w-0 truncate font-medium">{valueLabel}</span>
        </>
      ) : (
        <span className="text-body-small shrink-0 font-medium whitespace-nowrap">{label}</span>
      )}
      <DropdownIcon className={cn('size-5 shrink-0', active ? 'text-icon-primary' : 'text-icon-normal')} />
    </button>
  );
}
