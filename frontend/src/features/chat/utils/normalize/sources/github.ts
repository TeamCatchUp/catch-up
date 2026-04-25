import type { SourceResponse } from '@/features/chat/types';

import type { NormalizedIntegrationFields } from './common';

const getRepo = (source: SourceResponse) => {
  if (source.owner && source.repo) return `${source.owner}/${source.repo}`;
  return source.repo?.trim() ?? '';
};

const getTitle = (source: SourceResponse) => {
  if (source.title) return source.title;
  if (source.entity_type === 'pr' && source.number) return `PR #${source.number}`;
  if ((source.entity_type === 'issue' || source.entity_type === 'comment') && source.number) {
    return `Issue #${source.number}`;
  }
  return '';
};

export const normalizeGithubFields = (source: SourceResponse): NormalizedIntegrationFields => {
  const githubNumber = source.entity_type === 'pr' || source.entity_type === 'issue' ? source.number : undefined;

  return {
    repo: getRepo(source),
    title: getTitle(source),
    author: source.author ?? '',
    github_number: githubNumber,
  };
};
