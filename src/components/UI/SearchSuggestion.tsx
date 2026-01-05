interface SearchSuggestionProps {
  title: string;
}

export const SearchSuggestion = ({ title }: SearchSuggestionProps) => (
  <div className="flex flex-col items-start gap-2.5 self-stretch">
    <div className="flex items-center justify-center gap-2.5 px-1.5">
      <div className="text-nomal-alternative text-body-small">{title}</div>
    </div>
  </div>
);
