export interface SlackUserMetadata {
  id: string;
  name?: string | null;
  display_name?: string | null;
  profile_image_url?: string | null;
}

export interface SlackTextStyleRaw {
  bold?: boolean;
  italic?: boolean;
  strike?: boolean;
  code?: boolean;
  underline?: boolean;
}

export type SlackRichTextElementRaw =
  | { type: 'text'; text?: string; style?: SlackTextStyleRaw }
  | { type: 'link'; url?: string; text?: string; style?: SlackTextStyleRaw }
  | { type: 'user'; user_id?: string; style?: SlackTextStyleRaw }
  | { type: 'channel'; channel_id?: string; style?: SlackTextStyleRaw }
  | { type: 'usergroup'; usergroup_id?: string; style?: SlackTextStyleRaw }
  | { type: 'emoji'; name?: string; unicode?: string }
  | { type: 'date'; timestamp?: number; format?: string; fallback?: string }
  | { type: 'broadcast'; range?: string }
  | { type: string; [key: string]: unknown };

export interface SlackRichTextSectionRaw {
  type: 'rich_text_section';
  elements?: SlackRichTextElementRaw[];
}

export interface SlackRichTextListRaw {
  type: 'rich_text_list';
  style?: 'bullet' | 'ordered';
  indent?: number;
  offset?: number;
  elements?: SlackRichTextSectionRaw[];
}

export interface SlackRichTextQuoteRaw {
  type: 'rich_text_quote';
  elements?: SlackRichTextElementRaw[];
}

export interface SlackRichTextPreformattedRaw {
  type: 'rich_text_preformatted';
  elements?: SlackRichTextElementRaw[];
  border?: number;
}

export type SlackRichTextBlockElementRaw =
  | SlackRichTextSectionRaw
  | SlackRichTextListRaw
  | SlackRichTextQuoteRaw
  | SlackRichTextPreformattedRaw
  | { type: string; [key: string]: unknown };

export interface SlackBlockTextRaw {
  type?: string;
  text?: string;
}

export interface SlackBlockRaw {
  type?: string;
  block_id?: string;
  elements?: SlackRichTextBlockElementRaw[];
  text?: SlackBlockTextRaw;
  fields?: SlackBlockTextRaw[];
  image_url?: string;
  alt_text?: string;
  title?: SlackBlockTextRaw;
}

export interface SlackFileRaw {
  id?: string;
  name?: string;
  title?: string;
  filetype?: string;
  mimetype?: string;
  size?: number;
  permalink?: string;
  url_private?: string;
  url_private_download?: string;
  thumb_360?: string;
  thumb_480?: string;
}

export interface SlackAttachmentRaw {
  id?: number | string;
  fallback?: string;
  title?: string;
  title_link?: string;
  text?: string;
  pretext?: string;
  author_name?: string;
  service_name?: string;
  from_url?: string;
  footer?: string;
  color?: string;
  image_url?: string;
  thumb_url?: string;
}

export interface SlackEditedRaw {
  user?: string;
  ts?: string;
}

export interface SlackMessageIconsRaw {
  image_36?: string;
  image_48?: string;
  image_72?: string;
}

export interface SlackBotProfileRaw {
  id?: string;
  app_id?: string;
  name?: string;
  icons?: SlackMessageIconsRaw;
}

export interface SlackMessageRaw {
  type?: string;
  subtype?: string;
  user?: string;
  username?: string;
  bot_id?: string;
  bot_profile?: SlackBotProfileRaw;
  icons?: SlackMessageIconsRaw;
  text?: string;
  ts: string;
  thread_ts?: string;
  reply_count?: number;
  reply_users?: string[];
  files?: SlackFileRaw[];
  attachments?: SlackAttachmentRaw[];
  blocks?: SlackBlockRaw[];
  edited?: SlackEditedRaw;
}

export interface SlackOriginalRawItem {
  id: string;
  type: 'slack_conversations_replies_raw';
  raw_payload: {
    ok?: boolean;
    messages?: SlackMessageRaw[];
    response_metadata?: { next_cursor?: string };
  };
  created_at: string | null;
  updated_at: string | null;
}

export interface SlackOriginalContentResponse {
  connector: 'slack';
  entity_type: 'message';
  document_id: string;
  title: string;
  url: string | null;
  items: SlackOriginalRawItem[];
  metadata: {
    team_id: string;
    channel_id: string;
    thread_ts: string;
    channel_name?: string;
    workspace_domain?: string;
    users_by_id: Record<string, SlackUserMetadata>;
  };
  next_cursor: string | null;
  fetched_at: string;
}
