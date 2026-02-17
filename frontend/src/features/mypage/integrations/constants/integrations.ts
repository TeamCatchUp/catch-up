import type { IntegrationAccountMeta } from '../types/integrations';

import IconConfluence from '/public/icons/logo/Counfluence.svg';
import IconGithub from '/public/icons/logo/GitHub.svg';
import IconJira from '/public/icons/logo/Jira.svg';
import IconSlack from '/public/icons/logo/Slack.svg';
import ImgAPItoken from '/public/image/apitoken_figma.png';
import ImgAPItoken1 from '/public/image/apitoken1_figma.png';

/** 연동 계정 카드 목록 메타 데이터 */
export const INTEGRATION_ACCOUNTS: IntegrationAccountMeta[] = [
  { service: 'jira', name: 'Jira', Icon: IconJira },
  { service: 'github', name: 'Github', Icon: IconGithub },
  { service: 'slack', name: 'Slack', Icon: IconSlack },
  { service: 'confluence', name: 'Confluence', Icon: IconConfluence },
];

/** Atlassian 계정 관리 페이지 링크 */
export const ATLASSIAN_PROFILE_URL = 'https://id.atlassian.com/manage-profile/profile-and-visibility';

/** Jira 가이드 이미지 리소스 */
export const JIRA_GUIDE_IMAGES = {
  token: ImgAPItoken,
  tokenSetting: ImgAPItoken1,
};
