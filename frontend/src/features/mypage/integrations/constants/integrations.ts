export { INTEGRATION_ACCOUNTS } from '@/shared/constants/integrationAccounts';

import ImgGuideIntegrationPage from '/public/image/guide_integration_page.png';
import ImgGuideProjectSpace from '/public/image/guide_project_space.png';
import ImgGuideGithubIntegrationPage from '/public/image/guide_github_integration_page.png';
import ImgGuideGithubAppInstall from '/public/image/guide_github_app_install.png';
import ImgGuideGithubRepository from '/public/image/guide_github_repository.png';
import ImgGuideSlackIntegrationPage from '/public/image/guide_slack_integration_page.png';

/** Atlassian 계정 관리 페이지 링크 */
export const ATLASSIAN_PROFILE_URL = 'https://id.atlassian.com/manage-profile/profile-and-visibility';

/** GitHub 계정 관리 페이지 링크 */
export const GITHUB_PROFILE_URL = 'https://github.com/apps/catchup-connector';

/** Jira 가이드 이미지 리소스 */
export const JIRA_GUIDE_IMAGES = {
  integrationPage: ImgGuideIntegrationPage,
  projectSpace: ImgGuideProjectSpace,
};

/** GitHub 가이드 이미지 리소스 */
export const GITHUB_GUIDE_IMAGES = {
  integrationPage: ImgGuideGithubIntegrationPage,
  appInstall: ImgGuideGithubAppInstall,
  repository: ImgGuideGithubRepository,
};

/** Slack 가이드 이미지 리소스 */
export const SLACK_GUIDE_IMAGES = {
  integrationPage: ImgGuideSlackIntegrationPage,
};
