import type { SourceResponseApi } from '@/shared/types/sourceApi';

import type { NormalizedIntegrationFields } from './common';

const getRepo = (source: SourceResponseApi) => {
  if (source.entity_type === 'document_article') return source.space_name ?? '';
  return source.channel_name ?? '';
};

export const normalizeChannelTalkFields = (source: SourceResponseApi): NormalizedIntegrationFields => ({
  repo: getRepo(source),
  title: source.title ?? '',
  author: source.author ?? '',
});
