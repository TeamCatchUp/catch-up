interface SearchOptionButtonProps {
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  label: string;
}

export const SearchOptionButton = ({ Icon, label }: SearchOptionButtonProps) => (
  <button className="border-neutral-3 hover:bg-neutral-1 flex h-9 max-w-36 cursor-pointer items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5 transition-colors">
    <Icon className="h-5 w-5" />
    <div className="text-gray-80 text-body-small whitespace-nowrap">{label}</div>
  </button>
);
