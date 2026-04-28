import type { SourceResponse } from '@/features/chat/types';

import type { NormalizedIntegrationFields } from './common';

export const normalizeConfluenceFields = (source: SourceResponse): NormalizedIntegrationFields => ({
  repo: source.space_name ?? source.space_key ?? 'Confluence',
  title: source.title ?? 'Confluence 문서',
  author: source.author ?? '',
});
