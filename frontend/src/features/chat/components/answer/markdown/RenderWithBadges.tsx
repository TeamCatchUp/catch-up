import type { ChatSource } from '@/features/chat/types';

import SourceBadge, { SourceType } from './SourceBadge';

const CITATION_PATTERN = /\[(\d+)\]/g;

export const getCitationDisplayOrderMap = (text: string, validIndices?: Set<number>) => {
  const map = new Map<number, number>();
  const matches = text.matchAll(CITATION_PATTERN);

  for (const match of matches) {
    const sourceIndex = Number(match[1]);
    if (!Number.isFinite(sourceIndex) || map.has(sourceIndex)) continue;
    if (validIndices && !validIndices.has(sourceIndex)) continue;
    map.set(sourceIndex, map.size + 1);
  }

  return map;
};

export const renderWithBadges = (
  text: string,
  sources?: ChatSource[],
  citationOrderMap?: Map<number, number>,
): React.ReactNode => {
  if (!sources?.length) return text;

  const sourceMap = new Map<number, ChatSource>();
  sources.forEach((source) => {
    sourceMap.set(source.source_index, source);
  });

  const displayOrderMap = citationOrderMap ?? getCitationDisplayOrderMap(text);
  const parts = text.split(/(\[\d+\])/g);

  return (
    <>
      {parts.map((part, index) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (!match) return <span key={index}>{part}</span>;

        const sourceIndex = Number(match[1]);
        const source = sourceMap.get(sourceIndex);
        if (!source) return <span key={index}>{part}</span>;

        const badgeType: SourceType =
          source.source_type === 'jira'
            ? 'jira'
            : source.source_type === 'slack'
              ? 'slack'
              : source.source_type === 'confluence'
                ? 'confluence'
                : source.source_type === 'channel_talk'
                  ? 'channel_talk'
                  : 'github';

        return (
          <SourceBadge key={index} n={String(displayOrderMap.get(sourceIndex) ?? sourceIndex)} sourceType={badgeType} />
        );
      })}
    </>
  );
};
