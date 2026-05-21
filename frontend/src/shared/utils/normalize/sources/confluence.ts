import type { SourceResponseApi } from '@/shared/types/sourceApi';

import type { NormalizedIntegrationFields } from './common';

export const normalizeConfluenceFields = (source: SourceResponseApi): NormalizedIntegrationFields => ({
  repo: source.space_name ?? source.space_key ?? 'Confluence',
  title: source.title ?? 'Confluence 문서',
  author: source.author ?? '',
});
