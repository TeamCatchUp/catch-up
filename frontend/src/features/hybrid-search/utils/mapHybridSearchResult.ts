// SourceResponseApi → HybridSearchResultCard props 변환.
// source별로 contextLabel, identifier 구성 방식이 다르다.

import type { DocsSource } from '@/shared/types/source';
import type { SourceResponseApi } from '@/shared/types/sourceApi';
import { formatRelativeTime } from '@/shared/utils/formatDate';

// API에서 'unknown'이 올 수 있어 표시 영역은 fallback 카드로 처리.
export type CardSourceType = DocsSource | 'unknown';

export interface HybridSearchResultCardData {
  id: string;
  sourceType: CardSourceType;
  integrationLabel: string;
  contextLabel: string;
  title: string;
  url: string;
  author: string;
  changedAt: string;
  identifier?: string;
}

const INTEGRATION_LABELS: Record<CardSourceType, string> = {
  jira: 'Jira',
  github: 'Github',
  slack: 'Slack',
  confluence: 'Confluence',
  channel_talk: '채널톡',
  unknown: '기타',
};

function buildContextLabel(src: SourceResponseApi): string {
  switch (src.source) {
    case 'jira':
      return src.project_key ?? '';
    case 'github':
      if (src.owner && src.repo) return `${src.owner}/${src.repo}`;
      return src.repo ?? '';
    case 'slack':
      return src.channel_name ? `#${src.channel_name}` : '';
    case 'confluence':
      return src.space_name ?? '';
    case 'channel_talk':
      return src.channel_name ?? '';
    default:
      return '';
  }
}

function buildIdentifier(src: SourceResponseApi): string | undefined {
  if (src.source === 'jira' && src.issue_key) return `[${src.issue_key}]`;
  if (src.source === 'github' && src.number != null) return `#${src.number}`;
  return undefined;
}

// 'unknown' source는 fallback 카드로 표시 (제네릭 아이콘 + "기타" 라벨).
export function mapHybridSearchResult(src: SourceResponseApi): HybridSearchResultCardData {
  const sourceType: CardSourceType = src.source === 'unknown' ? 'unknown' : (src.source as DocsSource);
  return {
    id: src.id,
    sourceType,
    integrationLabel: INTEGRATION_LABELS[sourceType],
    contextLabel: buildContextLabel(src),
    title: src.title,
    url: src.url ?? '',
    author: src.author ?? '',
    changedAt: src.updated_at ? formatRelativeTime(src.updated_at) : '',
    identifier: buildIdentifier(src),
  };
}
