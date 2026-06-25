import React, { forwardRef } from 'react';

import { cn } from '@/shared/utils/cn';

interface SearchOptionButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
  selected?: boolean;
  // 아이콘 사이즈 등을 override할 때 사용 (기본 h-5 w-5)
  iconClassName?: string;
}

interface DisabledButtonProps {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
}

export const SearchOptionButton = forwardRef<HTMLButtonElement, SearchOptionButtonProps>(
  ({ Icon, label, selected = false, onClick, className, iconClassName, ...props }, ref) => {
    return (
      <button
        ref={ref}
        onClick={onClick}
        {...props}
        className={cn(
          'flex h-9 max-w-40 shrink-0 cursor-pointer items-center justify-center gap-1 rounded-lg border border-solid px-2 py-1.5 transition-colors',
          selected
            ? 'border-line-primary-normal bg-fill-primary-normal-assistive'
            : 'border-line-normal-neutral bg-fill-normal-normal',
          !selected &&
            'hover:border-line-normal-neutral hover:bg-fill-normal-interaction-hover active:border-line-normal-neutral active:bg-fill-normal-interaction-pressed',
          className,
        )}
      >
        <Icon
          className={cn(
            'h-5 w-5 shrink-0',
            selected ? 'text-icon-primary-normal' : 'text-icon-normal-normal',
            iconClassName,
          )}
        />
        <div
          className={cn(
            'text-body-small truncate whitespace-nowrap',
            selected ? 'text-text-primary-normal' : 'text-text-normal-normal',
          )}
        >
          {label}
        </div>
      </button>
    );
  },
);

SearchOptionButton.displayName = 'SearchOptionButton';

export const SearchOptionDisabledButton = ({ label, Icon }: DisabledButtonProps) => {
  return (
    <button
      disabled
      className="border-line-normal-neutral bg-fill-normal-strong flex h-9 max-w-40 shrink-0 cursor-pointer items-center justify-center gap-1 rounded-lg border border-solid px-2 py-1.5"
    >
      <Icon className="text-text-normal-assistive size-5 shrink-0" />
      <div className="text-body-small text-text-normal-alternative truncate whitespace-nowrap">{label}</div>
    </button>
  );
};
