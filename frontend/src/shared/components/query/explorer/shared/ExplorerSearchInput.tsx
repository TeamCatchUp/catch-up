import IconSearch from '@/public/icons/icon/search.svg';

interface ExplorerSearchProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}

export const ExplorerSearchInput = ({ value, onChange, placeholder }: ExplorerSearchProps) => {
  return (
    <div className="border-neutral-5 flex h-9 w-68.25 items-center gap-1 rounded-xl border bg-white px-2.5 py-1.5">
      <IconSearch className="h-5 w-5 shrink-0 text-gray-50" />
      <input
        className="text-body-small placeholder:text-gray-40 w-full truncate outline-none"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
};
