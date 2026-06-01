import type {
  SlackAttachmentRaw,
  SlackFileRaw,
  SlackTextStyleRaw,
  SlackUserMetadata,
} from '@/features/hybrid-search/types/slackOriginalApi';

export type SlackRichTextToken =
  | { type: 'text'; text: string; style?: SlackTextStyleRaw }
  | { type: 'mention'; label: string; style?: SlackTextStyleRaw }
  | { type: 'link'; href: string; text: string; style?: SlackTextStyleRaw }
  | { type: 'emoji'; label: string }
  | { type: 'line_break' };

export type SlackAvatarSource = 'user_profile' | 'bot_profile' | 'message_icons' | 'none';

export type SlackBlockView =
  | { type: 'paragraph'; tokens: SlackRichTextToken[] }
  | { type: 'bullet_list'; items: SlackRichTextToken[][] }
  | { type: 'ordered_list'; items: SlackRichTextToken[][]; start: number }
  | { type: 'quote'; tokens: SlackRichTextToken[] }
  | { type: 'code_block'; text: string };

export interface SlackMessageView {
  id: string;
  ts: string;
  threadTs: string | null;
  author: {
    id: string | null;
    name: string;
    avatarUrl: string | null;
    avatarSource: SlackAvatarSource;
    kind: 'user' | 'bot' | 'unknown';
  };
  timeLabel: string;
  editedLabel: string;
  dateKey: string;
  blocks: SlackBlockView[];
  files: SlackFileRaw[];
  attachments: SlackAttachmentRaw[];
}

export interface SlackThreadView {
  documentId: string;
  title: string;
  url: string | null;
  channelName: string;
  participantNames: string[];
  commentCount: number;
  usersById: Record<string, SlackUserMetadata>;
  messages: SlackMessageView[];
}
