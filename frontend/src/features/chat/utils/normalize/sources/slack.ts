import type { SourceResponse } from '@/features/chat/types';

import type { NormalizedIntegrationFields } from './common';

export const normalizeSlackFields = (source: SourceResponse): NormalizedIntegrationFields => ({
  repo: source.channel_name ?? '',
  title: source.title ?? 'Slack 메시지',
  author: source.author ?? '',
});
