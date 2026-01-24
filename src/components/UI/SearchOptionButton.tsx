import React, { forwardRef } from 'react';
import clsx from 'clsx';

interface SearchOptionButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
  selected?: boolean;
}

interface DisabledButtonProps {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
}

export const SearchOptionButton = forwardRef<HTMLButtonElement, SearchOptionButtonProps>(
  ({ Icon, label, selected = false, onClick, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        onClick={onClick}
        {...props}
        className={clsx(
          'flex h-9 max-w-40 shrink-0 cursor-pointer items-center justify-center gap-1 rounded-lg border border-solid px-2 py-1.5 transition-colors',
          selected ? 'border-blue-30 bg-blue-1' : 'border-neutral-3 bg-white',
          !selected && 'hover:border-neutral-3 hover:bg-neutral-2 active:border-neutral-3 active:bg-neutral-3',
          className,
        )}
      >
        <Icon className={clsx('h-5 w-5 shrink-0', selected ? 'text-blue-55' : 'text-gray-70')} />
        <div className={clsx('text-body-small truncate whitespace-nowrap', selected ? 'text-blue-55' : 'text-gray-80')}>
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
      className="border-neutral-3 bg-neutral-1 flex h-9 max-w-40 shrink-0 cursor-pointer items-center justify-center gap-1 rounded-lg border border-solid px-2 py-1.5"
    >
      <Icon className="text-gray-30 shrink-0" />
      <div className="text-body-small truncate whitespace-nowrap text-gray-50">{label}</div>
    </button>
  );
};
