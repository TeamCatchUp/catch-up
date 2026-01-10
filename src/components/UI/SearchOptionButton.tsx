import clsx from 'clsx';

interface SearchOptionButtonProps {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
  selected?: boolean;
  onClick?: () => void;
}

export const SearchOptionButton = ({ Icon, label, selected = false, onClick }: SearchOptionButtonProps) => (
  <button
    onClick={onClick}
    className={clsx(
      'flex h-9 max-w-40 cursor-pointer items-center justify-center gap-1 rounded-lg border border-solid px-2 py-1.5 transition-colors',
      selected ? 'border-blue-30 bg-blue-1' : 'border-neutral-3 bg-white',
      !selected && 'hover:border-neutral-3 hover:bg-neutral-2 active:border-neutral-3 active:bg-neutral-3',
    )}
  >
    <Icon className={clsx('h-5 w-5 shrink-0', selected ? 'text-blue-55' : 'text-gray-70')} />
    <div className={clsx('text-body-small truncate whitespace-nowrap', selected ? 'text-blue-55' : 'text-gray-80')}>
      {label}
    </div>
  </button>
);
