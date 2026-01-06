interface SearchSuggestionProps {
  title: string;
  suggestions: string[];
  onItemClick: (question: string) => void;
}

export const SearchSuggestion = ({ title, suggestions, onItemClick }: SearchSuggestionProps) => (
  <div className="flex flex-col items-start gap-2.5 self-stretch">
    <div className="flex items-center justify-center gap-2.5 px-1.5">
      <div className="text-nomal-alternative text-body-small">{title}</div>
    </div>
    {suggestions.map((question, index) => (
      <button
        key={index}
        onClick={() => onItemClick(question)}
        className="hover:bg-neutral-1 text-body-medium text-gray-70 rounded-md px-1 py-2 text-left"
      >
        {question}
      </button>
    ))}
  </div>
);
