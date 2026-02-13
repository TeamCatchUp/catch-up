import type { MockSource } from './types';

/**
 * UI 렌더링용 Mock 소스 데이터 (ChatSource 형태, 9개 항목)
 * SourceList 컴포넌트에서 시각적 레이아웃 테스트에 사용
 *
 * 사용처:
 * - MOCK_INITIAL_MESSAGES의 답변에 포함 (sources 필드)
 */
const MOCK_CHAT_SOURCES: ChatSource[] = [
  {
    id: 'mock-src-1',
    source_type: 'code',
    is_cited: true,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/main/java/AuthController.java',
    source_index: 1,
  },
  {
    id: 'mock-src-2',
    source_type: 'pr',
    is_cited: true,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-FE/pull/42',
    source_index: 2,
  },
  {
    id: 'mock-src-3',
    source_type: 'jira',
    is_cited: true,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    html_url: 'https://jira.catchup.io/browse/CATCH-101',
    date: '3일 전 변경',
    author: '작성자 명',
    source_index: 3,
  },
  {
    id: 'mock-src-4',
    source_type: 'github_issue',
    is_cited: true,
    repo: 'Slack 채널 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    html_url: 'https://slack.com/archives/C12345678/p1730000000000000',
    date: '3일 전 변경',
    author: '작성자 명',
    source_index: 4,
  },
  {
    id: 'mock-src-5',
    source_type: 'code',
    is_cited: false,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/service/AuthService.ts',
    source_index: 5,
  },
  {
    id: 'mock-src-6',
    source_type: 'pr',
    is_cited: false,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-FE/pull/55',
    source_index: 6,
  },
  {
    id: 'mock-src-7',
    source_type: 'jira',
    is_cited: false,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://jira.catchup.io/browse/CATCH-202',
    source_index: 7,
  },
  {
    id: 'mock-src-8',
    source_type: 'github_issue',
    is_cited: false,
    repo: 'Slack workspace text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://slack.com/archives/C87654321/p1731111111000000',
    source_index: 8,
  },
  {
    id: 'mock-src-9',
    source_type: 'code',
    is_cited: false,
    repo: '레포지토리명 text text text text text text text text text text text text text text',
    title: '일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 Kic일본 시장 진출 KicKic일본 시장 진출 Kic',
    content:
      'text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text',
    date: '3일 전 변경',
    author: '작성자 명',
    html_url: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/repository/UserRepository.ts',
    source_index: 9,
  },
];

/**
 * 백엔드 응답 형태 Mock 소스 데이터 (MockSource[] 타입, 3개 항목)
 * SSE 응답 및 RAG 답변 생성 시뮬레이션에 사용
 *
 * 사용처:
 * - mockChatService.ts - streamChat(), resumeStream()의 sources 응답
 * - sseSimulator.ts - SSE 이벤트 스트림의 sources 데이터
 */
export const MOCK_SOURCES: MockSource[] = [
  {
    index: 0,
    is_cited: true,
    source_type: 0,
    relevance_score: 0.95,
    html_url: 'https://github.com/TeamCatchUp/CatchUp-BE/blob/main/src/rag/service/RagService.ts',
    content: `export class RagService {
  async processQuery(query: string, sessionId: string): Promise<RagResponse> {
    // 1. 벡터 검색으로 관련 문서 조회
    const documents = await this.vectorStore.search(query, { limit: 10 });

    // 2. Reranker로 관련도 재평가
    const reranked = await this.reranker.rank(query, documents);

    // 3. LLM으로 답변 생성
    const answer = await this.llm.generate({
      query,
      context: reranked.slice(0, 5),
      chatHistory: await this.getChatHistory(sessionId),
    });

    return { answer, sources: reranked };
  }
}`,
    owner: 'TeamCatchUp',
    repo: 'CatchUp-BE',
    file_path: 'src/rag/service/RagService.ts',
    category: 'service',
    language: 'typescript',
  },
  {
    index: 1,
    is_cited: true,
    source_type: 1,
    relevance_score: 0.88,
    html_url: 'https://github.com/TeamCatchUp/CatchUp-FE/pull/156',
    content: `## 변경사항
- RagAnswer 컴포넌트 구현 (마크다운 렌더링, 소스 인용)
- SourceList UI 개선 (cited/uncited 구분 표시)
- 피드백 버튼 추가 (좋아요/싫어요)

## 스크린샷
[이미지 첨부]

## 테스트
- [x] 마크다운 렌더링 확인
- [x] 소스 인용 [1], [2] 클릭 시 해당 소스로 스크롤
- [x] 피드백 제출 정상 동작`,
    owner: 'TeamCatchUp',
    repo: 'CatchUp-FE',
    title: 'feat(chat): RAG 답변 UI 컴포넌트 구현',
    pr_number: 156,
    state: 'merged',
    created_at: 1738454400,
    author: '팀원E',
  },
  {
    index: 2,
    is_cited: true,
    source_type: 3,
    relevance_score: 0.82,
    html_url: 'https://jira.catchup.io/browse/CAT-296',
    content: 'RAG 답변 생성 시 인용 소스가 5개 이상일 경우 cited/uncited 영역 구분이 필요합니다. 현재는 모든 소스가 동일하게 표시되어 사용자가 실제 인용된 소스를 파악하기 어렵습니다.',
    owner: 'CATCH',
    repo: '',
    issueTypeName: 'Story',
    summary: 'RAG 답변 소스 cited/uncited 구분 표시',
    project_name: 'CatchUp',
    issue_key: 'CAT-296',
    parent_key: 'CAT-200',
    parent_summary: 'Q1 RAG 기능 개선',
    status_id: 3,
    assignee_name: '정성훈',
  },
];

/**
 * RAG 답변 마크다운 예시 텍스트
 * 소스 인용([1], [2], [3])과 마크다운 렌더링 테스트용
 *
 * 사용처:
 * - MOCK_INITIAL_MESSAGES의 첫 번째 답변 content (mock-a1)
 */
export const MOCK_RAG_ANSWER = `## RAG 답변 생성 프로세스

CatchUp의 RAG(Retrieval-Augmented Generation) 시스템은 다음과 같은 단계로 동작합니다:

### 1. 벡터 검색 (Retrieval)
사용자 질문이 입력되면 **\`RagService\`**[1]에서 벡터 DB를 검색하여 관련 문서를 조회합니다.

\`\`\`typescript
const documents = await this.vectorStore.search(query, { limit: 10 });
\`\`\`

### 2. 관련도 재평가 (Reranking)
검색된 문서들을 Reranker 모델로 재평가하여 상위 5개를 선택합니다[1].

### 3. 답변 생성 (Generation)
선택된 문서를 컨텍스트로 LLM이 답변을 생성합니다. 이때 채팅 히스토리도 함께 참고하여 문맥을 유지합니다[1].

### 4. UI 렌더링
생성된 답변은 마크다운 형태로 표시되며, 인용된 소스는 cited 영역에 강조 표시됩니다[2][3].

### 참고사항
- 벡터 검색 모델: OpenAI text-embedding-3-large
- Reranker 모델: Cohere rerank-multilingual-v3.0
- LLM: GPT-4 Turbo
`;

/**
 * 관련 Jira 이슈 Mock 데이터 (MockSource[] 타입, 1개 항목)
 * PR 선택 후 재질문 시나리오 테스트용
 *
 * 사용처:
 * - 현재 미사용 (향후 PR 컨텍스트 기반 재질문 기능에서 활용 예정)
 */
export const MOCK_RELATED_JIRA_ISSUES: MockSource[] = [
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
    content: 'useEffect의 cleanup 함수는 언제 실행되나요?useEffect의 cleanup 함수는 언제 실행되나요?useEffect의 cleanup 함수는 언제 실행되나요?useEffect의 cleanup 함수는 언제 실행되나요?',
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
