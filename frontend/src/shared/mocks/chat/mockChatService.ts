import delay from '@/shared/mocks/delay';

const MOCK_SOURCES: BackendSource[] = [
  {
    index: 1,
    is_cited: true,
    source_type: 1,
    relevance_score: 0.95,
    html_url: 'https://github.com/example/repo/pull/42',
    content: 'feat: 로그인 토큰 갱신 로직 개선',
    owner: 'example',
    repo: 'CatchUp-BE',
    title: 'feat: 로그인 토큰 갱신 로직 개선',
    pr_number: 42,
    created_at: Date.now() - 86400000,
    author: 'developer',
  },
  {
    index: 2,
    is_cited: true,
    source_type: 0,
    relevance_score: 0.88,
    html_url: 'https://github.com/example/repo/blob/main/src/auth/service.ts',
    content: 'export class AuthService { ... }',
    owner: 'example',
    repo: 'CatchUp-BE',
    file_path: 'src/auth/service.ts',
    author: 'developer',
  },
  {
    index: 3,
    is_cited: true,
    source_type: 3,
    relevance_score: 0.82,
    html_url: 'https://catchup.atlassian.net/browse/CAT-101',
    content: '로그인 관련 이슈',
    owner: 'catchup',
    issue_key: 'CAT-101',
    summary: '로그인 시 토큰 만료 처리 개선',
    project_name: 'CatchUp',
    assignee_name: '홍길동',
  },
];

const buildMockAnswer = (query: string) =>
  `# H1: "${query}"에 대한 답변

## H2: 텍스트 스타일

일반 텍스트입니다. **볼드 텍스트**, *이탤릭 텍스트*, ***볼드+이탤릭***, ~~취소선 텍스트~~, \`인라인 코드\`를 포함합니다.

소스 인용 테스트: 관련 PR [1], 코드 파일 [2], Jira 이슈 [3]

### H3: 순서 없는 리스트

- 항목 1
- 항목 2
  - 중첩 항목 2-1
  - 중첩 항목 2-2
    - 깊은 중첩 항목
- 항목 3

### H3: 순서 있는 리스트

1. 첫 번째 단계
2. 두 번째 단계
   1. 하위 단계 2-1
   2. 하위 단계 2-2
3. 세 번째 단계

#### H4: 체크박스 리스트

- [x] 완료된 작업
- [x] 또 다른 완료 작업
- [ ] 미완료 작업
- [ ] 남은 작업

## H2: 코드 블록

TypeScript:

\`\`\`typescript
interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

export class AuthService {
  async refreshToken(token: string): Promise<TokenPair> {
    const decoded = this.jwtService.verify(token);
    return this.generateTokenPair(decoded.userId);
  }
}
\`\`\`

Python:

\`\`\`python
def fibonacci(n: int) -> list[int]:
    """피보나치 수열 생성"""
    seq = [0, 1]
    for i in range(2, n):
        seq.append(seq[i-1] + seq[i-2])
    return seq[:n]
\`\`\`

JSON:

\`\`\`json
{
  "name": "CatchUp",
  "version": "1.0.0",
  "dependencies": {
    "next": "^16.1.6",
    "@tanstack/react-query": "^5.0.0"
  }
}
\`\`\`

## H2: 인용구 (Blockquote)

> 단일 인용구입니다. **볼드**와 \`코드\`도 포함할 수 있습니다.

> 중첩 인용구:
> > 안쪽 인용구입니다.
> > 여러 줄도 가능합니다.

## H2: 테이블

| 기능 | 상태 | 담당자 |
|------|:----:|-------:|
| 로그인 | 완료 | 홍길동 |
| 회원가입 | 진행 중 | 김철수 |
| 토큰 갱신 | 완료 | 이영희 |
| 비밀번호 재설정 | 미시작 | - |

## H2: 구분선

위 내용

---

아래 내용

## H2: 링크

[GitHub 저장소](https://github.com/example/repo)와 일반 URL https://catchup.example.com 자동 링크

> **참고**: 이 답변은 Mock 데이터 기반입니다. 실제 백엔드 연동 시 RAG 파이프라인을 통해 더 정확한 답변이 생성됩니다.`;

const mockChatService = {
  streamChat: async (
    query: string,
    sessionId: string,
    onEvent: (event: StreamEvent) => void,
  ) => {
    console.log('[mockChatService] streamChat:', { query, sessionId });

    await delay(500);
    onEvent({ type: 'status', node: 'router', message: '질문 분석 중...' });
    await delay(500);
    onEvent({ type: 'status', node: 'retrieve', message: '문서 검색 중...' });
    await delay(500);
    onEvent({ type: 'status', node: 'rerank', message: '관련도 평가 중...' });
    await delay(500);
    onEvent({ type: 'status', node: 'generate', message: '답변 생성 중...' });
    await delay(300);
    onEvent({
      type: 'result',
      answer: buildMockAnswer(query),
      sources: MOCK_SOURCES,
      chat_history_id: `mock-history-${Date.now()}`,
      has_feedback: false,
    });
  },

  resumeStream: async (
    sessionId: string,
    selectedPRs: { pr_number: number; repo_name: string; owner: string }[],
    onEvent: (event: StreamEvent) => void,
  ) => {
    console.log('[mockChatService] resumeStream:', { sessionId, selectedPRs });

    await delay(500);
    onEvent({ type: 'status', node: 'generate', message: 'PR 컨텍스트로 답변 생성 중...' });
    await delay(500);
    onEvent({
      type: 'result',
      answer: `## PR 기반 답변\n\nPR ${selectedPRs.map((p) => `#${p.pr_number}`).join(', ')}을 분석한 결과입니다.\n\n### 변경 사항 요약\n- 선택된 PR의 코드 변경사항을 반영한 답변입니다.\n- 관련 컨텍스트를 포함하여 생성되었습니다.\n\n> **참고**: Mock 데이터 기반 답변입니다.`,
      sources: MOCK_SOURCES.slice(0, 1),
      chat_history_id: `mock-history-${Date.now()}`,
      has_feedback: false,
    });
  },
};

export default mockChatService;
