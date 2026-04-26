import type { SourceResponse } from '@/features/chat/types';

import type { NormalizedIntegrationFields } from './common';

/**
 * 백엔드가 channel_name=null로 보낼 때 text 본문에서 채널명 fallback 추출.
 * text 예: "[2026-04-13 06:41:17]\nAuthor: 팀원B\nChannel: #slack-bot-test\n..."
 */
const parseChannelFromText = (text?: string | null) => {
  if (!text) return '';
  const match = text.match(/Channel:\s*(#?\S+)/);
  return match?.[1] ?? '';
};

export const normalizeSlackFields = (source: SourceResponse): NormalizedIntegrationFields => ({
  repo: source.channel_name ?? parseChannelFromText(source.text),
  title: source.title ?? 'Slack 메시지',
  author: source.author ?? '',
});
