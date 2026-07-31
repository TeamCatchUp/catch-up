import IconChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import IconConfluence from '@/public/icons/logo/Confluence.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';

import type { IntegrationService } from '../types/integrationModel';

/**
 * 커넥터 브랜드 로고.
 * `embeddingUtils`의 `RESOURCE_ICONS`와 다르다 — 그쪽은 리소스 행에 쓰는
 * 채널/스페이스 아이콘이고, 이쪽은 도구 자체의 로고다.
 */
export const CONNECTOR_LOGOS: Record<IntegrationService, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  slack: IconSlack,
  jira: IconJira,
  github: IconGithub,
  confluence: IconConfluence,
  channel_talk: IconChannelTalk,
};
