import type {
  SlackMessageIconsRaw,
  SlackMessageRaw,
  SlackOriginalContentResponse,
  SlackUserMetadata,
} from '@/features/hybrid-search/types/slackOriginalApi';
import type {
  SlackAvatarSource,
  SlackMessageView,
  SlackThreadView,
} from '@/features/hybrid-search/types/slackOriginalModel';

import { parseSlackBlocks } from './parseSlackBlocks';
import { parseSlackTextFallback } from './parseSlackTextFallback';
import { formatSlackDateKey, formatSlackEditedLabel, formatSlackMessageTime } from './slackTimestamp';

interface ResolvedAvatar {
  url: string | null;
  source: SlackAvatarSource;
}

function pickSlackIconUrl(icons: SlackMessageIconsRaw | undefined): string | null {
  return icons?.image_36 ?? icons?.image_48 ?? icons?.image_72 ?? null;
}

function resolveBotAvatar(
  message: SlackMessageRaw,
  usersById: Record<string, SlackUserMetadata>,
): ResolvedAvatar {
  const userProfileUrl = message.user ? (usersById[message.user]?.profile_image_url ?? null) : null;

  if (userProfileUrl) {
    return { url: userProfileUrl, source: 'user_profile' };
  }

  const botProfileUrl = pickSlackIconUrl(message.bot_profile?.icons);

  if (botProfileUrl) {
    return { url: botProfileUrl, source: 'bot_profile' };
  }

  const messageIconsUrl = pickSlackIconUrl(message.icons);

  if (messageIconsUrl) {
    return { url: messageIconsUrl, source: 'message_icons' };
  }

  return { url: null, source: 'none' };
}

function resolveAuthor(
  message: SlackMessageRaw,
  usersById: Record<string, SlackUserMetadata>,
): SlackMessageView['author'] {
  if (message.bot_id || message.bot_profile || message.subtype === 'bot_message') {
    const avatar = resolveBotAvatar(message, usersById);

    return {
      id: message.bot_id ?? message.bot_profile?.id ?? null,
      name: message.bot_profile?.name ?? message.username ?? 'Slack Bot',
      avatarUrl: avatar.url,
      avatarSource: avatar.source,
      kind: 'bot',
    };
  }

  const user = message.user ? usersById[message.user] : undefined;
  const avatarUrl = user?.profile_image_url ?? null;

  return {
    id: message.user ?? null,
    name: user?.display_name || user?.name || message.user || '알 수 없음',
    avatarUrl,
    avatarSource: avatarUrl ? 'user_profile' : 'none',
    kind: message.user ? 'user' : 'unknown',
  };
}

function collectMessages(response: SlackOriginalContentResponse): SlackMessageRaw[] {
  return response.items.flatMap((item) => item.raw_payload.messages ?? []);
}

function participantNames(messages: SlackMessageRaw[], usersById: Record<string, SlackUserMetadata>): string[] {
  const names = new Set<string>();

  for (const message of messages) {
    const author = resolveAuthor(message, usersById);
    if (author.name) names.add(author.name);
  }

  return Array.from(names);
}

function resolveCommentCount(messages: SlackMessageRaw[]): number {
  const parentReplyCount = messages[0]?.reply_count;
  if (typeof parentReplyCount === 'number') return Math.max(parentReplyCount, 0);

  return Math.max(messages.length - 1, 0);
}

function parseMessage(message: SlackMessageRaw, usersById: Record<string, SlackUserMetadata>): SlackMessageView {
  const parsedBlocks = parseSlackBlocks(message.blocks, usersById);
  const fallbackBlocks = parseSlackTextFallback(message.text ?? '', usersById);

  return {
    id: message.ts,
    ts: message.ts,
    threadTs: message.thread_ts ?? null,
    author: resolveAuthor(message, usersById),
    timeLabel: formatSlackMessageTime(message.ts),
    editedLabel: formatSlackEditedLabel(message.edited?.ts),
    dateKey: formatSlackDateKey(message.ts),
    blocks: parsedBlocks.length > 0 ? parsedBlocks : fallbackBlocks,
    files: message.files ?? [],
    attachments: message.attachments ?? [],
  };
}

export function parseSlackOriginalThread(response: SlackOriginalContentResponse): SlackThreadView {
  const usersById = response.metadata.users_by_id;
  const messages = collectMessages(response);

  return {
    documentId: response.document_id,
    title: response.title,
    url: response.url,
    channelName: response.metadata.channel_name || response.metadata.channel_id,
    participantNames: participantNames(messages, usersById),
    commentCount: resolveCommentCount(messages),
    usersById,
    messages: messages.map((message) => parseMessage(message, usersById)),
  };
}
