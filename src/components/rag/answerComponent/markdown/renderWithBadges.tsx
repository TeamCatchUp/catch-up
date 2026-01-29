import SourceBadge, { SourceType } from './SourceBadge';

export const renderWithBadges = (text: string, sources?: ChatSource[]): React.ReactNode => {
  console.log('renderWithBadges called:', { text, sourcesLength: sources?.length });

  if (!sources?.length) {
    console.log('No sources, returning plain text');
    return text;
  }

  const sourceMap = new Map<number, ChatSource>();
  sources.forEach((s) => {
    console.log('Source mapping:', s.sourceIndex, s);
    sourceMap.set(s.sourceIndex, s);
  });

  const parts = text.split(/(\[\d+\])/g);
  console.log('Split parts:', parts);

  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);

        if (!match) {
          console.log(`Plain text part ${i}:`, part);
          return <span key={i}>{part}</span>;
        }

        const num = Number(match[1]);
        const source = sourceMap.get(num);

        console.log(`Badge part ${i}:`, { num, hasSource: !!source, sourceType: source?.sourceType });

        if (!source) {
          console.log(`No source found for index ${num}`);
          return <span key={i}>{part}</span>;
        }

        const badgeType: SourceType = source.sourceType === 'jira' ? 'jira' : 'github';

        return <SourceBadge key={i} n={String(num)} sourceType={badgeType} />;
      })}
    </>
  );
};
