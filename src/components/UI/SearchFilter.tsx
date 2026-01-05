interface FilterChipProps {
  label: string;
}

export const FilterChip = ({ label }: FilterChipProps) => (
  <button className="rounded-rounded border-blue-30 bg-blue-1 transition-hover hover:bg-blue-5 flex h-9 items-center justify-center gap-1.5 border border-solid px-3 py-1.5">
    {label}
  </button>
);
