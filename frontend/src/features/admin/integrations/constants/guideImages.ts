import ImgGuideConfluenceIntegrationPage from '@/public/image/guide/guide_confluence_integration_page.png';
import ImgGuideGithubIntegrationPage from '@/public/image/guide/guide_github_integration_page.png';
import ImgGuideGithubRepository from '@/public/image/guide/guide_github_repository.png';
import ImgGuideGithubRepositoryInstall from '@/public/image/guide/guide_github_repository_install.png';
import ImgGuideJiraIntegrationPage from '@/public/image/guide/guide_jira_integration_page.png';
import ImgGuideSlackIntegrationPage from '@/public/image/guide/guide_slack_integration_page.png';
import ImgGuideSlackPermissions from '@/public/image/guide/guide_slack_permissions.png';

// 가이드 이미지 static import는 components/management/guides/의 4개 파일만 쓴다.
// integrationsConfig에 함께 두면 RESOURCES_PER_PAGE나 INTEGRATION_ACCOUNTS를 쓰는 모듈까지
// PNG를 전부 끌고 오게 되고, Storybook의 vite next-image 변환이 Windows 경로에서 깨진다.

/** Jira 가이드 이미지 리소스 */
export const JIRA_GUIDE_IMAGES = {
  integrationPage: ImgGuideJiraIntegrationPage,
};

/** GitHub 가이드 이미지 리소스 */
export const GITHUB_GUIDE_IMAGES = {
  integrationPage: ImgGuideGithubIntegrationPage,
  repository: ImgGuideGithubRepository,
  repositoryInstall: ImgGuideGithubRepositoryInstall,
};

/** Slack 가이드 이미지 리소스 */
export const SLACK_GUIDE_IMAGES = {
  integrationPage: ImgGuideSlackIntegrationPage,
  permissions: ImgGuideSlackPermissions,
};

/** Confluence 가이드 이미지 리소스 */
export const CONFLUENCE_GUIDE_IMAGES = {
  integrationPage: ImgGuideConfluenceIntegrationPage,
};
