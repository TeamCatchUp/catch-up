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

// UI용 Mock Source 데이터 (ChatSource 형태, SourceList 렌더링용)
const MOCK_CHAT_SOURCES: ChatSource[] = [
  {
    id: 'mock-src-1',
    source_type: 'code',
    is_cited: true,
    repo: 'CatchUp-BE',
    title: 'AuthController.java',
    content: `public class AuthController {
  @PostMapping("/login")
  public ResponseEntity<TokenDto> login(@RequestBody LoginRequest request) {
    return authService.authenticate(request);
  }
}`,
    date: '3일 전 변경',
    author: '김백엔드',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/AuthController.java',
    source_index: 0,
  },
  {
    id: 'mock-src-2',
    source_type: 'pr',
    is_cited: true,
    repo: 'CatchUp-FE',
    title: 'feat: 로그인 페이지 리뉴얼',
    content: `## 변경사항\n- 로그인 폼 UI 개선\n- 에러 메시지 표시 개선\n- 로딩 상태 추가`,
    date: '2026.01.12',
    author: '이프론트',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-FE/pull/42',
    source_index: 1,
  },
  {
    id: 'mock-src-3',
    source_type: 'jira',
    is_cited: true,
    repo: '',
    title: '소셜 로그인 버그 수정',
    content: '소셜 로그인 시 간헐적으로 토큰이 발급되지 않는 버그가 발생합니다.',
    date: '2026.01.10',
    author: '최QA',
    html_url: 'https://jira.catchup.io/browse/CATCH-101',
    source_index: 2,
  },
];

// 백엔드 응답 형태 Mock Source 데이터 (SSE 시뮬레이터용)
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

/**
 * 다중 QA 테스트용 초기 메시지 (3쌍)
 * 연속 스크롤 검증에 사용
 */
export const MOCK_INITIAL_MESSAGES: Message[] = [
  {
    id: 'mock-q1',
    role: 'user',
    content: '로그인 인증 흐름을 설명해주세요',
    timestamp: '2026-02-12T09:00:00Z',
  },
  {
    id: 'mock-a1',
    chat_history_id: 'mock-history-001',
    role: 'assistant',
    content: MOCK_RAG_ANSWER,
    sources: MOCK_CHAT_SOURCES,
    detailed_tasks: [],
    timestamp: '2026-02-12T09:00:05Z',
    has_feedback: false,
  },
  {
    id: 'mock-q2',
    role: 'user',
    content: 'Refresh Token 갱신 로직은 어떻게 구현되어 있나요?',
    timestamp: '2026-02-12T09:01:00Z',
  },
  {
    id: 'mock-a2',
    chat_history_id: 'mock-history-002',
    role: 'assistant',
    content: `## Refresh Token 갱신 로직

### 갱신 흐름
1. Access Token 만료 시 클라이언트가 \`/api/auth/refresh\` 엔드포인트 호출
2. 서버에서 Refresh Token 유효성 검증
3. 새로운 Access Token + Refresh Token 발급 (Rotation 방식)

### 코드 구현
\`\`\`java
@PostMapping("/refresh")
public ResponseEntity<TokenDto> refresh(@CookieValue String refreshToken) {
    // 1. Refresh Token 검증
    Claims claims = jwtProvider.validateToken(refreshToken);

    // 2. 토큰 블랙리스트 확인
    if (tokenBlacklist.contains(refreshToken)) {
        throw new InvalidTokenException("이미 사용된 토큰입니다");
    }

    // 3. 새 토큰 쌍 발급
    TokenDto newTokens = authService.rotateTokens(claims.getSubject());

    // 4. 기존 Refresh Token 블랙리스트 등록
    tokenBlacklist.add(refreshToken);

    return ResponseEntity.ok(newTokens);
}
\`\`\`

### 보안 사항
- **Token Rotation**: 갱신 시마다 새 Refresh Token 발급, 기존 토큰 무효화
- **블랙리스트**: Redis로 관리, Refresh Token 유효기간(7일) 후 자동 삭제
- **동시 요청 처리**: 분산 락으로 동일 Refresh Token 동시 사용 방지`,
    sources: MOCK_CHAT_SOURCES,
    detailed_tasks: [],
    timestamp: '2026-02-12T09:01:05Z',
    has_feedback: false,
  },
  {
    id: 'mock-q3',
    role: 'user',
    content: 'OAuth 2.0 소셜 로그인 연동 방법을 알려주세요',
    timestamp: '2026-02-12T09:02:00Z',
  },
  {
    id: 'mock-a3',
    chat_history_id: 'mock-history-003',
    role: 'assistant',
    content: `## OAuth 2.0 소셜 로그인 연동

### 지원 Provider
- **Google**: 메인 로그인 (필수)
- **GitHub**: 개발자 계정 연동 (선택)

### 인증 흐름 (Authorization Code Grant)

\`\`\`
사용자 → 프론트엔드 → OAuth Provider → 백엔드 → DB
  1. 로그인 버튼 클릭
  2. OAuth Provider 로그인 페이지 리다이렉트
  3. 사용자 인증 + 동의
  4. Authorization Code 발급
  5. 백엔드에서 Code → Access Token 교환
  6. Provider API로 사용자 정보 조회
  7. 자체 JWT 토큰 발급
\`\`\`

### 백엔드 구현
\`\`\`java
@GetMapping("/oauth2/callback/{provider}")
public ResponseEntity<Void> oauthCallback(
    @PathVariable String provider,
    @RequestParam String code
) {
    // Provider별 토큰 교환
    OAuthTokenResponse token = oauthClient.exchangeCode(provider, code);

    // 사용자 정보 조회
    OAuthUserInfo userInfo = oauthClient.getUserInfo(provider, token);

    // 회원 가입/조회 + JWT 발급
    TokenDto jwt = authService.processOAuthLogin(userInfo);

    return ResponseEntity.ok().header("Set-Cookie", jwt.toCookie()).build();
}
\`\`\`

### 프론트엔드 구현
\`\`\`typescript
const handleGoogleLogin = () => {
  window.location.href = \`\${API_BASE}/oauth2/authorize/google\`;
};
\`\`\``,
    sources: MOCK_CHAT_SOURCES,
    detailed_tasks: [],
    timestamp: '2026-02-12T09:02:05Z',
    has_feedback: false,
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
