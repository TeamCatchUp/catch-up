import type { MappingUploadResponse, UserSyncStatusResponse } from '@/features/mypage/integrations/types/api';

/** mock 표시 시 반드시 포함할 상태 집합 (CSV 업로드 후 상태) */
export const REQUIRED_MOCK_MEMBER_STATUSES = ['완료', '미사용'] as const;

/** 이용자 연동 목록 mock 상태 패턴 (CSV 업로드 후: 완료 or 미사용만) */
export const MOCK_MEMBER_STATUS_PATTERNS = [
  { github: '미사용', jira: '완료', slack: '미사용', confluence: '미사용' },
  { github: '완료', jira: '완료', slack: '완료', confluence: '미사용' },
  { github: '미사용', jira: '완료', slack: '미사용', confluence: '미사용' },
] as const;

/** GET /api/v1/admin/users/sync-status mock 응답 */
export const MOCK_USER_SYNC_STATUS: UserSyncStatusResponse = {
  counts: {
    github: { users: 24, premap: 16 },
    jira: { users: 24, premap: 20 },
    slack: { users: 24, premap: 14 },
    confluence: { users: 24, premap: 8 },
  },
  mappings: [
    // 전체 연동
    { name: '직원04', githubLogin: 'minsu-kim', atlassianEmail: 'minsu@company.com', slackEmail: 'minsu@company.com' },
    { name: '최서연', githubLogin: 'seoyeon-choi', atlassianEmail: 'seoyeon@company.com', slackEmail: 'seoyeon@company.com' },
    { name: '한소희', githubLogin: 'sohee-han', atlassianEmail: 'sohee@company.com', slackEmail: 'sohee@company.com' },
    { name: '임태호', githubLogin: 'taeho-lim', atlassianEmail: 'taeho@company.com', slackEmail: 'taeho@company.com' },
    { name: '배지윤', githubLogin: 'jiyoon-bae', atlassianEmail: 'jiyoon@company.com', slackEmail: 'jiyoon@company.com' },
    { name: '조현우', githubLogin: 'hyunwoo-jo', atlassianEmail: 'hyunwoo@company.com', slackEmail: 'hyunwoo@company.com' },
    { name: '서민지', githubLogin: 'minji-seo', atlassianEmail: 'minji@company.com', slackEmail: 'minji@company.com' },
    { name: '류승호', githubLogin: 'seungho-ryu', atlassianEmail: 'seungho@company.com', slackEmail: 'seungho@company.com' },
    // 부분 연동
    { name: '이지현', githubLogin: 'jihyun-lee', atlassianEmail: 'jihyun@company.com', slackEmail: null },
    { name: '박준영', githubLogin: null, atlassianEmail: 'junyoung@company.com', slackEmail: 'junyoung@company.com' },
    { name: '정우진', githubLogin: null, atlassianEmail: null, slackEmail: 'woojin@company.com' },
    { name: '윤도현', githubLogin: 'dohyun-yoon', atlassianEmail: null, slackEmail: null },
    { name: '직원02', githubLogin: null, atlassianEmail: 'yerin@company.com', slackEmail: 'yerin@company.com' },
    { name: '오성민', githubLogin: 'sungmin-oh', atlassianEmail: 'sungmin@company.com', slackEmail: null },
    { name: '문채원', githubLogin: 'chaewon-moon', atlassianEmail: null, slackEmail: 'chaewon@company.com' },
    { name: '황진우', githubLogin: null, atlassianEmail: 'jinwoo@company.com', slackEmail: null },
    { name: '안수빈', githubLogin: 'subin-ahn', atlassianEmail: null, slackEmail: 'subin@company.com' },
    { name: '노유정', githubLogin: null, atlassianEmail: 'yujeong@company.com', slackEmail: 'yujeong@company.com' },
    { name: '권혁준', githubLogin: 'hyukjun-kwon', atlassianEmail: 'hyukjun@company.com', slackEmail: null },
    { name: '장다은', githubLogin: 'daeun-jang', atlassianEmail: null, slackEmail: null },
    // 미연동
    { name: '송하나', githubLogin: null, atlassianEmail: null, slackEmail: null },
    { name: '백시우', githubLogin: null, atlassianEmail: null, slackEmail: null },
    { name: '고은서', githubLogin: null, atlassianEmail: null, slackEmail: null },
    { name: '신태영', githubLogin: null, atlassianEmail: null, slackEmail: null },
  ],
};

/** 서비스별 계정 후보 mock (수정 모드 드롭다운용) */
export const MOCK_ACCOUNT_OPTIONS_BY_SERVICE = {
  github: [
    { name: '직원04', email: 'minsu-kim' },
    { name: '이지현', email: 'jihyun-lee' },
    { name: '최서연', email: 'seoyeon-choi' },
    { name: '한소희', email: 'sohee-han' },
    { name: '윤도현', email: 'dohyun-yoon' },
    { name: '오성민', email: 'sungmin-oh' },
    { name: '배지윤', email: 'jiyoon-bae' },
    { name: '임태호', email: 'taeho-lim' },
  ],
  jira: [
    { name: '직원04', email: 'minsu@company.com' },
    { name: '이지현', email: 'jihyun@company.com' },
    { name: '박준영', email: 'junyoung@company.com' },
    { name: '최서연', email: 'seoyeon@company.com' },
    { name: '한소희', email: 'sohee@company.com' },
    { name: '직원02', email: 'yerin@company.com' },
    { name: '오성민', email: 'sungmin@company.com' },
    { name: '배지윤', email: 'jiyoon@company.com' },
  ],
  slack: [
    { name: '직원04', email: 'minsu@company.com' },
    { name: '박준영', email: 'junyoung@company.com' },
    { name: '최서연', email: 'seoyeon@company.com' },
    { name: '정우진', email: 'woojin@company.com' },
    { name: '한소희', email: 'sohee@company.com' },
    { name: '직원02', email: 'yerin@company.com' },
    { name: '임태호', email: 'taeho@company.com' },
    { name: '배지윤', email: 'jiyoon@company.com' },
  ],
};

/** POST /api/v1/mapping/{vendor}/upload mock 응답 */
export const MOCK_MAPPING_UPLOAD_RESPONSE: MappingUploadResponse = {
  status: 'success',
  file_type: 'csv',
  stats: {
    csv_rows_skipped: 1,
    total_success: 10,
    total_failed: 0,
    new_mappings: 7,
    updated_mappings: 3,
  },
};
