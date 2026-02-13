import type { BackendSource } from '@/features/chat/types/source';
import { formatDate, formatFullDate } from '@/shared/utils/formatDate';

const getUiSourceType = (source: BackendSource['source'], entityType: string): ChatSource['source_type'] => {
  if (source === 'github') {
    if (entityType === 'code') return 'code';
    if (entityType === 'pr') return 'pr';
    if (entityType === 'issue' || entityType === 'comment') return 'github_issue';
  }

  if (source === 'slack' && entityType === 'message') return 'slack';
  if (source === 'jira') return 'jira';

  return 'code';
};

const getLastPath = (path?: string) => {
  if (!path) return '';
  const cleaned = path.replace(/\+$/, '');
  return cleaned.split('/').pop() ?? cleaned;
};

const formatDaysAgo = (daysAgo?: number) => {
  if (typeof daysAgo !== 'number') return '';
  return `${daysAgo}일 전 변경`;
};

const formatCreatedAt = (createdAt?: number | string) => {
  if (createdAt === null || createdAt === undefined || createdAt === '') return '';

  if (typeof createdAt === 'number') {
    return formatDate(createdAt);
  }

  const trimmed = createdAt.trim();
  if (!trimmed) return '';

  const asNumber = Number(trimmed);
  if (!Number.isNaN(asNumber) && Number.isFinite(asNumber)) {
    return formatDate(asNumber);
  }

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }

  return formatFullDate(parsed.toISOString());
};

const getSourceLink = (source: BackendSource) => source.html_url ?? source.url ?? '';

const getSourceContent = (source: BackendSource) =>
  source.citation_rationale?.trim() || source.content?.trim() || source.text?.trim() || '';

const getRepoText = (source: BackendSource, sourceType: ChatSource['source_type']) => {
  if (sourceType === 'slack') {
    return source.channel_name ?? source.repo ?? '';
  }

  if (source.owner && source.repo) {
    return `${source.owner}/${source.repo}`;
  }

  return source.repo ?? '';
};

const getTitleText = (source: BackendSource, sourceType: ChatSource['source_type']) => {
  if (sourceType === 'pr') {
    return source.title ?? (source.number ? `PR #${source.number}` : '');
  }

  if (sourceType === 'jira') {
    if (source.issue_key && source.summary) {
      return `[${source.issue_key}] ${source.summary}`;
    }
    return source.title ?? source.summary ?? source.issue_key ?? '';
  }

  if (sourceType === 'code') {
    return getLastPath(source.file_path) || source.title || '';
  }

  if (sourceType === 'slack') {
    return source.title ?? 'Slack 메시지';
  }

  return source.title ?? (source.number ? `Issue #${source.number}` : '');
};

export const normalizeSources = (sources: BackendSource[]): ChatSource[] => {
  return (sources ?? []).map((source, index) => {
    const sourceType = getUiSourceType(source.source, source.entity_type);

    const date =
      sourceType === 'code'
        ? formatDaysAgo(source.days_ago) || formatCreatedAt(source.created_at)
        : formatCreatedAt(source.created_at);

    const author =
      sourceType === 'code'
        ? source.author ?? ''
        : source.assignee_name ?? source.assignee ?? source.author ?? '';

    return {
      id: crypto.randomUUID(),
      source_type: sourceType,
      is_cited: source.is_cited ?? false,
      repo: getRepoText(source, sourceType),
      title: getTitleText(source, sourceType),
      content: getSourceContent(source),
      date,
      author,
      html_url: getSourceLink(source),
      source_index: typeof source.index === 'number' ? source.index : index + 1,
    };
  });
};
