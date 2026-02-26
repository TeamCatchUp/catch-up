/** 협업툴 연동 카드에 사용하는 샘플 계정 정보 */
export const MOCK_INTEGRATION_ACCOUNT_INFO = {
  userName: '직원20',
  userId: 'IDtexttexttexttexttexttexttexttext',
  userEmail: 'dlkjfcccldjl@gmail.comcomcomcom',
};

/** 서비스별 연동 계정 목데이터 (jira만 연결, 나머지 미연결) */
export const MOCK_ACCOUNT_INFO_MAP: Record<string, { userName: string; userId: string; userEmail: string }> = {
  jira: MOCK_INTEGRATION_ACCOUNT_INFO,
  github: { userName: '-', userId: '-', userEmail: '-' },
  slack: { userName: '-', userId: '-', userEmail: '-' },
  confluence: { userName: '-', userId: '-', userEmail: '-' },
};

/** 계정 선택 드롭다운용 목데이터 */
export const MOCK_SELECTABLE_ROWS = [
  {
    userKey: 'u1',
    userName: '직원20',
    email: 'yumi.lee@company.com',
    phone: '010-1234-5678',
    department: '개발팀',
    teamSizeLabel: '8명',
    picture: null,
    accountIdByService: { github: 'yumi.lee@gmail.com', jira: 'yumi.lee@gmail.com', slack: 'yumi.lee@gmail.com' },
    statusByService: {
      jira: '완료' as const,
      github: '완료' as const,
      slack: '완료' as const,
      confluence: '미사용' as const,
    },
  },
  {
    userKey: 'u2',
    userName: '직원04',
    email: 'minsu.kim@company.com',
    phone: '010-2345-6789',
    department: '기획팀',
    teamSizeLabel: '5명',
    picture: null,
    accountIdByService: { github: 'minsu.kim@gmail.com', jira: 'minsu.kim@gmail.com', slack: 'minsu.kim@gmail.com' },
    statusByService: {
      jira: '완료' as const,
      github: '미사용' as const,
      slack: '완료' as const,
      confluence: '완료' as const,
    },
  },
  {
    userKey: 'u3',
    userName: '직원10',
    email: 'seoyeon.park@company.com',
    phone: '010-3456-7890',
    department: '디자인팀',
    teamSizeLabel: '4명',
    picture: null,
    accountIdByService: {
      github: 'seoyeon.park@gmail.com',
      jira: 'seoyeon.park@gmail.com',
      slack: 'seoyeon.park@gmail.com',
    },
    statusByService: {
      jira: '완료' as const,
      github: '미사용' as const,
      slack: '완료' as const,
      confluence: '미사용' as const,
    },
  },
  {
    userKey: 'u4',
    userName: '직원25',
    email: 'haneul.jung@company.com',
    phone: '010-4567-8901',
    department: '개발팀',
    teamSizeLabel: '8명',
    picture: null,
    accountIdByService: {
      github: 'haneul.jung@gmail.com',
      jira: 'haneul.jung@gmail.com',
      slack: 'haneul.jung@gmail.com',
    },
    statusByService: {
      jira: '완료' as const,
      github: '완료' as const,
      slack: '완료' as const,
      confluence: '완료' as const,
    },
  },
  {
    userKey: 'u5',
    userName: '직원28',
    email: 'jiho.choi@company.com',
    phone: '010-5678-9012',
    department: 'QA팀',
    teamSizeLabel: '3명',
    picture: null,
    accountIdByService: { github: 'jiho.choi@gmail.com', jira: 'jiho.choi@gmail.com', slack: 'jiho.choi@gmail.com' },
    statusByService: {
      jira: '완료' as const,
      github: '미사용' as const,
      slack: '완료' as const,
      confluence: '미사용' as const,
    },
  },
];
