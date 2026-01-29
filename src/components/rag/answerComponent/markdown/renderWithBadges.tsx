import SourceBadge, { SourceType } from './SourceBadge';

export const renderWithBadges = (text: string, sources?: ChatSource[]): React.ReactNode => {
  if (!sources?.length) return text;

  const sourceMap = new Map<number, ChatSource>();
  sources.forEach((s) => sourceMap.set(s.sourceIndex, s));

  const parts = text.split(/(\[\d+\])/g);

  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (!match) return part; // string도 ReactNode

    const num = Number(match[1]);
    const source = sourceMap.get(num);
    if (!source) return part;

    const badgeType: SourceType = source.sourceType === 'jira' ? 'jira' : 'github';

    return <SourceBadge key={i} n={String(num)} sourceType={badgeType} />;
  });
};
