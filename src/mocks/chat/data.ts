interface ClientSourceBase {
  index: number;
  isCited: boolean;
  sourceType: 0 | 1 | 3;
  relevanceScore: number;
  htmlUrl: string;
  content: string;
  owner: string;
  repo: string;
}

interface ClientCodeSource extends ClientSourceBase {
  sourceType: 0;
  filePath: string;
  category?: string;
  language?: string;
}

interface ClientPullRequestSource extends ClientSourceBase {
  sourceType: 1;
  title: string;
  prNumber: number;
  state?: string;
  createdAt: number;
  author: string;
}

interface ClientJiraIssueSource extends ClientSourceBase {
  sourceType: 3;
  issueTypeName?: string;
  summary: string;
  projectName: string;
  issueKey: string;
  parentKey?: string;
  parentSummary?: string;
  statusId?: number;
  assigneeName?: string;
}

type ClientSource = ClientCodeSource | ClientPullRequestSource | ClientJiraIssueSource;

// Mock Source 데이터
export const MOCK_SOURCES: ClientSource[] = [
  // Code Source (sourceType: 0)
  {
    index: 0,
    isCited: true,
    sourceType: 0,
    relevanceScore: 0.95,
    htmlUrl: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/AuthController.java',
    content: `public class AuthController {
  @PostMapping("/login")
  public ResponseEntity<TokenDto> login(@RequestBody LoginRequest request) {
    return authService.authenticate(request);
  }

  @PostMapping("/refresh")
  public ResponseEntity<TokenDto> refresh(@CookieValue String refreshToken) {
    return authService.refreshToken(refreshToken);
  }
}`,
    owner: 'TeamCatchUp',
    repo: 'CatchUp-BE',
    filePath: 'src/main/java/AuthController.java',
    category: 'controller',
    language: 'java',
  },
  // PR Source (sourceType: 1)
  {
    index: 1,
    isCited: true,
    sourceType: 1,
    relevanceScore: 0.88,
    htmlUrl: 'https://github.com/TeamCatchUp/CatchUp-FE/pull/42',
    content: `## 변경사항
- 로그인 폼 UI 개선
- 에러 메시지 표시 개선
- 로딩 상태 추가`,
    owner: 'TeamCatchUp',
    repo: 'CatchUp-FE',
    title: 'feat: 로그인 페이지 리뉴얼',
    prNumber: 42,
    state: 'merged',
    createdAt: 1705056000,
    author: '이프론트',
  },
  // Jira Source (sourceType: 3)
  {
    index: 2,
    isCited: true,
    sourceType: 3,
    relevanceScore: 0.82,
    htmlUrl: 'https://jira.catchup.io/browse/CATCH-101',
    content: '소셜 로그인 시 간헐적으로 토큰이 발급되지 않는 버그가 발생합니다. 재현 단계: 1) 구글 로그인 클릭 2) OAuth 완료 후 리다이렉트 3) 토큰이 undefined로 설정됨',
    owner: 'CATCH',
    repo: '',
    issueTypeName: 'Bug',
    summary: '소셜 로그인 버그 수정',
    projectName: 'CatchUp',
    issueKey: 'CATCH-101',
    parentKey: 'CATCH-100',
    parentSummary: '인증 시스템 개선',
    statusId: 3,
    assigneeName: '최QA',
  },
];

// Mock RAG 답변
export const MOCK_RAG_ANSWER = `## 인증 흐름 설명

CatchUp 서비스의 인증 흐름은 다음과 같습니다:

### 1. 로그인 요청
사용자가 로그인 폼을 제출하면 **\`AuthController\`**[1]에서 요청을 처리합니다.

\`\`\`java
@PostMapping("/login")
public ResponseEntity<TokenDto> login(@RequestBody LoginRequest request) {
    return authService.authenticate(request);
}
\`\`\`

### 2. 토큰 발급
인증 성공 시 JWT 토큰이 발급됩니다. 관련 PR[2]에서 토큰 갱신 로직이 개선되었습니다.

### 3. 관련 이슈
- 소셜 로그인 버그[3]가 최근 수정되었습니다

### 참고사항
- Access Token 유효기간: 30분
- Refresh Token 유효기간: 7일
`;

// Mock RAG Response
export const MOCK_RAG_RESPONSE = {
  sessionId: '', // 동적 설정
  answer: MOCK_RAG_ANSWER,
  sources: MOCK_SOURCES,
  chatHistoryId: 'mock-chat-history-001',
  hasFeedback: false,
};

// Mock Related Jira Issues
export const MOCK_RELATED_JIRA_ISSUES: ClientJiraIssueSource[] = [
  {
    index: 0,
    isCited: true,
    sourceType: 3,
    relevanceScore: 0.9,
    htmlUrl: 'https://jira.catchup.io/browse/CATCH-100',
    content: '인증 시스템 전반 개선 - OAuth 2.0 적용, 토큰 갱신 로직 개선, 보안 강화',
    owner: 'CATCH',
    repo: '',
    summary: '인증 시스템 개선',
    projectName: 'CatchUp',
    issueKey: 'CATCH-100',
    parentKey: 'CATCH-EPIC-01',
    parentSummary: '보안 강화 에픽',
  },
];

// Mock PR Candidates (인터럽트용)
export const MOCK_PR_CANDIDATES = [
  {
    prNumber: 42,
    title: 'feat: 로그인 페이지 리뉴얼',
    repoName: 'CatchUp-FE',
    summary: '로그인 폼 UI 개선 및 에러 처리 강화',
    owner: 'TeamCatchUp',
  },
  {
    prNumber: 38,
    title: 'fix: 토큰 갱신 버그 수정',
    repoName: 'CatchUp-BE',
    summary: 'Refresh Token 만료 시 처리 로직 수정',
    owner: 'TeamCatchUp',
  },
  {
    prNumber: 55,
    title: 'feat: OAuth 2.0 적용',
    repoName: 'CatchUp-BE',
    summary: '구글, 깃허브 소셜 로그인 지원',
    owner: 'TeamCatchUp',
  },
];
