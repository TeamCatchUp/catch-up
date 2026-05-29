import type { FC, SVGProps } from 'react';

import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import type { DocsSource } from '@/shared/types/source';

export interface SourceOption {
  value: DocsSource;
  label: string;
  Icon: FC<SVGProps<SVGSVGElement>>;
  iconClassName?: string;
}

export const SOURCE_OPTIONS: readonly SourceOption[] = [
  { value: 'github', label: 'Github', Icon: GitHub },
  { value: 'channel_talk', label: '채널톡', Icon: ChannelTalk, iconClassName: 'size-4' },
  { value: 'confluence', label: 'Confluence', Icon: Confluence },
  { value: 'jira', label: 'Jira', Icon: Jira },
  { value: 'slack', label: 'Slack', Icon: Slack },
];

export const SOURCE_LABELS = new Map(SOURCE_OPTIONS.map((source) => [source.value, source.label]));
