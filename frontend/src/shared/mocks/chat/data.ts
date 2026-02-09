interface ClientSourceBase {
  index: number;
  is_cited: boolean;
  source_type: 0 | 1 | 3;
  relevance_score: number;
  html_url: string;
  content: string;
  owner: string;
  repo: string;
}

interface ClientCodeSource extends ClientSourceBase {
  source_type: 0;
  file_path: string;
  category?: string;
  language?: string;
}

interface ClientPullRequestSource extends ClientSourceBase {
  source_type: 1;
  title: string;
  pr_number: number;
  state?: string;
  created_at: number;
  author: string;
}

interface ClientJiraIssueSource extends ClientSourceBase {
  source_type: 3;
  issueTypeName?: string;
  summary: string;
  project_name: string;
  issue_key: string;
  parent_key?: string;
  parent_summary?: string;
  status_id?: number;
  assignee_name?: string;
}

type ClientSource = ClientCodeSource | ClientPullRequestSource | ClientJiraIssueSource;

// Mock Source 데이터
export const MOCK_SOURCES: ClientSource[] = [
  {
    index: 0,
    is_cited: true,
    source_type: 0,
    relevance_score: 0.95,
    html_url: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/AuthController.java',
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
    file_path: 'src/main/java/AuthController.java',
    category: 'controller',
    language: 'java',
  },
  {
    index: 1,
    is_cited: true,
    source_type: 1,
    relevance_score: 0.88,
    html_url: 'https://github.com/TeamCatchUp/CatchUp-FE/pull/42',
    content: `## 변경사항
- 로그인 폼 UI 개선
- 에러 메시지 표시 개선
- 로딩 상태 추가`,
    owner: 'TeamCatchUp',
    repo: 'CatchUp-FE',
    title: 'feat: 로그인 페이지 리뉴얼',
    pr_number: 42,
    state: 'merged',
    created_at: 1705056000,
    author: '이프론트',
  },
  {
    index: 2,
    is_cited: true,
    source_type: 3,
    relevance_score: 0.82,
    html_url: 'https://jira.catchup.io/browse/CATCH-101',
    content: '소셜 로그인 시 간헐적으로 토큰이 발급되지 않는 버그가 발생합니다. 재현 단계: 1) 구글 로그인 클릭 2) OAuth 완료 후 리다이렉트 3) 토큰이 undefined로 설정됨',
    owner: 'CATCH',
    repo: '',
    issueTypeName: 'Bug',
    summary: '소셜 로그인 버그 수정',
    project_name: 'CatchUp',
    issue_key: 'CATCH-101',
    parent_key: 'CATCH-100',
    parent_summary: '인증 시스템 개선',
    status_id: 3,
    assignee_name: '최QA',
  },
];

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

export const MOCK_RAG_RESPONSE = {
  session_id: '',
  answer: MOCK_RAG_ANSWER,
  sources: MOCK_SOURCES,
  chat_history_id: 'mock-chat-history-001',
  has_feedback: false,
};

export const MOCK_RELATED_JIRA_ISSUES: ClientJiraIssueSource[] = [
  {
    index: 0,
    is_cited: true,
    source_type: 3,
    relevance_score: 0.9,
    html_url: 'https://jira.catchup.io/browse/CATCH-100',
    content: '인증 시스템 전반 개선 - OAuth 2.0 적용, 토큰 갱신 로직 개선, 보안 강화',
    owner: 'CATCH',
    repo: '',
    summary: '인증 시스템 개선',
    project_name: 'CatchUp',
    issue_key: 'CATCH-100',
    parent_key: 'CATCH-EPIC-01',
    parent_summary: '보안 강화 에픽',
  },
];

export const MOCK_PR_CANDIDATES = [
  {
    pr_number: 42,
    title: 'feat: 로그인 페이지 리뉴얼',
    repo_name: 'CatchUp-FE',
    summary: '로그인 폼 UI 개선 및 에러 처리 강화',
    owner: 'TeamCatchUp',
  },
  {
    pr_number: 38,
    title: 'fix: 토큰 갱신 버그 수정',
    repo_name: 'CatchUp-BE',
    summary: 'Refresh Token 만료 시 처리 로직 수정',
    owner: 'TeamCatchUp',
  },
  {
    pr_number: 55,
    title: 'feat: OAuth 2.0 적용',
    repo_name: 'CatchUp-BE',
    summary: '구글, 깃허브 소셜 로그인 지원',
    owner: 'TeamCatchUp',
  },
];
