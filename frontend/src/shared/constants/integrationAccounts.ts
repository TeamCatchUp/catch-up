import IconConfluence from '@/public/icons/logo/Confluence.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import type { IntegrationAccountMeta } from '@/shared/types/integrationService';

/** 연동 계정 카드 목록 메타 데이터 */
export const INTEGRATION_ACCOUNTS: IntegrationAccountMeta[] = [
  { service: 'jira', name: 'Jira', Icon: IconJira },
  { service: 'github', name: 'Github', Icon: IconGithub },
  { service: 'slack', name: 'Slack', Icon: IconSlack },
  { service: 'confluence', name: 'Confluence', Icon: IconConfluence },
];
