interface SearchOptionButtonProps {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
}

export const SearchOptionButton = ({ Icon, label }: SearchOptionButtonProps) => (
  <button className="border-neutral-3 hover:bg-neutral-1 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5 transition-colors">
    <Icon />
    <div className="text-gray-80 text-body-small whitespace-nowrap">{label}</div>
  </button>
);
