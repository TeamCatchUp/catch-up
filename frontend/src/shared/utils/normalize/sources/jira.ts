import type { SourceResponseApi } from '@/shared/types/sourceApi';

import { getFirstNonEmptyLine, type NormalizedIntegrationFields } from './common';

const JIRA_NO_TITLE_PATTERN = /\bno\s*title\b/i;

/** id 예: "jira:issue:CAT-145" */
const parseIssueKeyFromSourceId = (id?: string) => {
  const trimmed = id?.trim();
  if (!trimmed) return '';
  const match = trimmed.match(/^jira:[^:]+:([^:\s]+)$/i);
  return match?.[1] ?? '';
};

const getProjectKey = (source: SourceResponseApi) => {
  if (source.project_key?.trim()) return source.project_key.trim();
  if (source.issue_key?.trim()) return source.issue_key.trim().split('-')[0] ?? '';

  const issueKeyFromId = parseIssueKeyFromSourceId(source.id);
  if (issueKeyFromId.includes('-')) return issueKeyFromId.split('-')[0] ?? '';
  return '';
};

const parseTitleFromText = (text?: string | null) => {
  if (!text) return '';
  const firstLine = getFirstNonEmptyLine(text);
  return firstLine.startsWith('[') ? firstLine : '';
};

const parseAuthorFromText = (text?: string | null) => {
  if (!text) return '';

  const assignedMatch = text.match(/Assigned to:\s*([^|\n\r]+)/i);
  if (assignedMatch?.[1]) return assignedMatch[1].trim();

  const ownerMatch = text.match(/Owner:\s*([^\n\r]+)/i);
  if (ownerMatch?.[1]) return ownerMatch[1].trim();

  const reporterMatch = text.match(/Reporter:\s*([^|\n\r]+)/i);
  if (reporterMatch?.[1]) return reporterMatch[1].trim();

  return '';
};

const getTitle = (source: SourceResponseApi) => {
  const rawTitle = source.title?.trim() ?? '';
  if (rawTitle && !JIRA_NO_TITLE_PATTERN.test(rawTitle)) return rawTitle;

  const titleFromText = parseTitleFromText(source.text);
  if (titleFromText) return titleFromText;

  return source.issue_key ?? parseIssueKeyFromSourceId(source.id);
};

export const normalizeJiraFields = (source: SourceResponseApi): NormalizedIntegrationFields => {
  const issueKey = source.issue_key?.trim() || parseIssueKeyFromSourceId(source.id);
  const author = (source.assignee ?? source.author ?? parseAuthorFromText(source.text)) || '';

  return {
    repo: getProjectKey(source) || 'Jira',
    title: getTitle(source),
    author,
    issue_key: issueKey || undefined,
  };
};
