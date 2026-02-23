export { INTEGRATION_ACCOUNTS } from '@/shared/constants/integrationAccounts';

import ImgGuideJiraIntegrationPage from '/public/image/guide/guide_jira_integration_page.png';
import ImgGuideJiraConnectorInstall from '/public/image/guide/guide_jira_connector_install.png';
import ImgGuideJiraSiteSelection from '/public/image/guide/guide_jira_site_selection.png';
import ImgGuideJiraAccept from '/public/image/guide/guide_jira_accept.png';
import ImgGuideGithubIntegrationPage from '/public/image/guide/guide_github_integration_page.png';
import ImgGuideGithubInstall from '/public/image/guide/guide_github_install.png';
import ImgGuideGithubRepository from '/public/image/guide/guide_github_repository.png';
import ImgGuideSlackIntegrationPage from '/public/image/guide/guide_slack_integration_page.png';
import ImgGuideSlackPermissions from '/public/image/guide/guide_slack_permissions.png';
import ImgGuideConfluenceIntegrationPage from '/public/image/guide/guide_confluence_integration_page.png';
import ImgGuideConfluenceSiteSelection from '/public/image/guide/guide_confluence_site_selection.png';
import ImgGuideConfluenceAccept from '/public/image/guide/guide_confluence_accept.png';

/** Atlassian 계정 관리 페이지 링크 */
export const ATLASSIAN_PROFILE_URL = 'https://id.atlassian.com/manage-profile/profile-and-visibility';

/** GitHub 계정 관리 페이지 링크 */
export const GITHUB_PROFILE_URL = 'https://github.com/apps/catchup-connector';

/** Jira 가이드 이미지 리소스 */
export const JIRA_GUIDE_IMAGES = {
  integrationPage: ImgGuideJiraIntegrationPage,
  connectorInstall: ImgGuideJiraConnectorInstall,
  siteSelection: ImgGuideJiraSiteSelection,
  accept: ImgGuideJiraAccept,
};

/** GitHub 가이드 이미지 리소스 */
export const GITHUB_GUIDE_IMAGES = {
  integrationPage: ImgGuideGithubIntegrationPage,
  install: ImgGuideGithubInstall,
  repository: ImgGuideGithubRepository,
};

/** Slack 가이드 이미지 리소스 */
export const SLACK_GUIDE_IMAGES = {
  integrationPage: ImgGuideSlackIntegrationPage,
  permissions: ImgGuideSlackPermissions,
};

/** Confluence 가이드 이미지 리소스 */
export const CONFLUENCE_GUIDE_IMAGES = {
  integrationPage: ImgGuideConfluenceIntegrationPage,
  siteSelection: ImgGuideConfluenceSiteSelection,
  accept: ImgGuideConfluenceAccept,
};
