import SourceBadge, { SourceType } from './SourceBadge';

export const renderWithBadges = (text: string, sources?: ChatSource[]): React.ReactNode => {
  if (!sources?.length) {
    return text;
  }

  const sourceMap = new Map<number, ChatSource>();
  sources.forEach((s) => {
    sourceMap.set(s.source_index, s);
  });

  const parts = text.split(/(\[\d+\])/g);

  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);

        if (!match) {
          return <span key={i}>{part}</span>;
        }

        const num = Number(match[1]);
        const source = sourceMap.get(num);

        if (!source) {
          return <span key={i}>{part}</span>;
        }

        const badgeType: SourceType =
          source.source_type === 'jira'
            ? 'jira'
            : source.source_type === 'slack'
              ? 'slack'
              : 'github';

        return <SourceBadge key={i} n={String(num)} sourceType={badgeType} />;
      })}
    </>
  );
};
