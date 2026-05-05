import type { SourceResponse } from '@/features/chat/types';

import type { NormalizedIntegrationFields } from './common';

const getRepo = (source: SourceResponse) => {
  if (source.entity_type === 'document_article') return source.space_name ?? '';
  return source.channel_name ?? '';
};

export const normalizeChannelTalkFields = (source: SourceResponse): NormalizedIntegrationFields => ({
  repo: getRepo(source),
  title: source.title ?? '',
  author: source.author ?? '',
});
