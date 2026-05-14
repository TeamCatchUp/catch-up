// SourceResponseApi → HybridSearchResultCard props 변환.
// source별로 contextLabel, identifier 구성 방식이 다르다.

import type { DocsSource } from '@/shared/types/source';
import type { SourceResponseApi } from '@/shared/types/sourceApi';
import { formatRelativeTime } from '@/shared/utils/formatDate';

export interface HybridSearchResultCardData {
  sourceType: DocsSource;
  integrationLabel: string;
  contextLabel: string;
  title: string;
  url: string;
  author: string;
  changedAt: string;
  identifier?: string;
}

const INTEGRATION_LABELS: Record<DocsSource, string> = {
  jira: 'Jira',
  github: 'Github',
  slack: 'Slack',
  confluence: 'Confluence',
  channel_talk: '채널톡',
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

// 'unknown' source는 호출자가 filter — 매퍼는 DocsSource로 narrowing.
export function mapHybridSearchResult(src: SourceResponseApi): HybridSearchResultCardData {
  const sourceType = src.source as DocsSource;
  return {
    sourceType,
    integrationLabel: INTEGRATION_LABELS[sourceType] ?? src.source,
    contextLabel: buildContextLabel(src),
    title: src.title,
    url: src.url ?? '',
    author: src.author ?? '',
    changedAt: src.updated_at ? formatRelativeTime(src.updated_at) : '',
    identifier: buildIdentifier(src),
  };
}
