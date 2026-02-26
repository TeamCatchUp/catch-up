import { formatFullDate } from '@/shared/utils/formatDate';

import type { MockChatSource, MockMessage, MockSource } from './types';

/** 현재 시각 기준 N일 전 ISO 문자열 생성 */
const daysAgo = (n: number) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
};

export const MOCK_STREAM_STATUS_STEPS: Array<{ node: string; message: string }> = [
  { node: 'route', message: '질문 의도를 분석하고 있어요' },
  { node: 'rewrite', message: 'retrieval 정확도를 높이기 위해 질문을 정리하고 있어요' },
  { node: 'generate_vector_queries', message: 'vector query를 생성하고 있어요' },
  { node: 'search_vector_db', message: 'Vector DB에서 관련 문서를 찾고 있어요' },
  { node: 'rerank', message: '관련도 기준으로 문서를 다시 정렬하고 있어요' },
  { node: 'grade', message: '찾은 문서로 답변 가능한지 coverage를 확인하고 있어요' },
  { node: 'generate_final_answer', message: '최종 답변을 token stream으로 생성하고 있어요' },
];

export const MOCK_SOURCES: MockSource[] = [
  {
    id: 'github:pr:TeamCatchUp/CatchUp-BE:52',
    index: 1,
    is_cited: true,
    source: 'github',
    entity_type: 'pr',
    relevance_score: 0.94,
    url: 'https://github.com/TeamCatchUp/CatchUp-BE/pull/52',
    text: 'PR #52에서 채팅 답변의 status/sources/token 스트리밍 계약을 도입했습니다.',
    owner: 'TeamCatchUp',
    repo: 'CatchUp-BE',
    title: '[CAT-317] 채팅 스트리밍 이벤트(status/sources/token) 적용',
    number: 52,
    state: 'merged',
    created_at: daysAgo(14),
    author: '백엔드팀',
  },
  {
    id: 'jira:issue:CAT-299',
    index: 2,
    is_cited: false,
    source: 'jira',
    entity_type: 'issue',
    relevance_score: 0.87,
    url: 'https://catchup.atlassian.net/browse/CAT-299',
    text: 'cited/non-cited 분리 규칙과 출처 badge 순서 정책을 정의한 Jira 이슈입니다.',
    title: '[CAT-299] 인용 출처 렌더링 정책 정리',
    issue_key: 'CAT-299',
    project_key: 'CATCH',
    assignee: '기획팀',
    status: 'Done',
    created_at: daysAgo(5),
  },
  {
    id: 'slack:message:T001:C001:1739433600.000100',
    index: 3,
    is_cited: true,
    source: 'slack',
    entity_type: 'message',
    relevance_score: 0.92,
    url: 'https://catchup.slack.com/archives/C001/p1739433600000100',
    text: '백엔드는 status -> source 후보 -> token stream -> 최종 cited sources 순서로 이벤트를 보냅니다.',
    channel_name: 'frontend-dev',
    team_id: 'T001',
    ts: '1739433600.000100',
    title: '프론트/백엔드 스트리밍 동기화 메모',
    author: '프론트엔드팀',
    created_at: daysAgo(1),
  },
  {
    id: 'github:code:TeamCatchUp/CatchUp-FE:useRagChat',
    index: 4,
    is_cited: true,
    source: 'github',
    entity_type: 'code',
    relevance_score: 0.9,
    url: 'https://github.com/TeamCatchUp/CatchUp-FE/blob/main/src/features/chat/hooks/useRagChat.ts',
    text: '프론트는 스트리밍 token을 누적해 답변을 만들고 stream 종료 시 최종 상태를 확정합니다.',
    owner: 'TeamCatchUp',
    repo: 'CatchUp-FE',
    title: 'useRagChat: token 누적 및 종료 처리',
    author: '프론트엔드팀',
    created_at: daysAgo(0),
  },
  {
    id: 'jira:issue:CAT-321',
    index: 5,
    is_cited: false,
    source: 'jira',
    entity_type: 'issue',
    relevance_score: 0.72,
    url: 'https://catchup.atlassian.net/browse/CAT-321',
    text: '/api/chat/stream/resume 구현 진행 상태를 추적하는 Jira 이슈입니다.',
    title: '[CAT-321] Resume API 구현 추적',
    issue_key: 'CAT-321',
    project_key: 'CATCH',
    assignee: '백엔드팀',
    status: 'To Do',
    created_at: daysAgo(10),
  },
  {
    id: 'confluence:page:98765:chunk:0',
    index: 6,
    is_cited: true,
    source: 'confluence',
    entity_type: 'page',
    relevance_score: 0.89,
    url: 'https://catchup.atlassian.net/wiki/spaces/ENG/pages/98765',
    text: 'Title : RAG 파이프라인 아키텍처 가이드\nSpace: Engineering\n\n벡터 DB 검색 → 리랭킹 → 답변 생성 순서로 동작합니다.',
    title: 'RAG 파이프라인 아키텍처 가이드',
    citation_rationale: 'RAG 파이프라인의 전체 흐름(검색 → 리랭킹 → 답변 생성)을 설명하는 핵심 문서입니다.',
    author: 'backend-lead',
    created_at: daysAgo(3),
    space_id: '~12345',
    space_key: 'ENG',
    space_name: 'Engineering',
    version: 5,
    chunk_index: 0,
    total_chunks: 4,
    section_hierarchy: ['아키텍처', 'RAG 파이프라인'],
    has_images: false,
    image_urls: [],
  },
];

const toSourceType = (source: MockSource): MockChatSource['source_type'] => {
  if (source.source === 'github' && source.entity_type === 'code') return 'code';
  if (source.source === 'github' && source.entity_type === 'pr') return 'pr';
  if (source.source === 'slack' && source.entity_type === 'message') return 'slack';
  if (source.source === 'jira') return 'jira';
  if (source.source === 'confluence') return 'confluence';
  return 'github_issue';
};

const toSourceRepo = (source: MockSource) => {
  if (source.source === 'jira') {
    return source.project_key ?? source.issue_key ?? 'Jira';
  }

  if (source.source === 'slack') {
    return source.channel_name ?? 'Slack';
  }

  if (source.source === 'confluence') {
    return source.space_name ?? source.space_key ?? 'Confluence';
  }

  if (source.owner && source.repo) {
    return `${source.owner}/${source.repo}`;
  }

  return source.repo ?? '';
};

const toSourceTitle = (source: MockSource, sourceType: MockChatSource['source_type']) => {
  if (sourceType === 'pr') {
    return source.title ?? (source.number ? `PR #${source.number}` : '');
  }
  if (sourceType === 'jira') {
    return source.title ?? source.issue_key ?? '';
  }
  if (sourceType === 'code') {
    return source.title ?? '';
  }
  if (sourceType === 'slack') {
    return source.title ?? 'Slack 메시지';
  }
  if (sourceType === 'confluence') {
    return source.title ?? 'Confluence 문서';
  }
  return source.title ?? (source.number ? `Issue #${source.number}` : '');
};

const formatSourceDate = (source: MockSource) => {
  if (typeof source.created_at === 'string' && source.created_at.trim()) {
    return formatFullDate(source.created_at);
  }
  return '';
};

const toChatSource = (source: MockSource): MockChatSource => {
  const sourceType = toSourceType(source);
  return {
    id: `mock-source-${source.index}`,
    source_type: sourceType,
    is_cited: source.is_cited ?? false,
    repo: toSourceRepo(source),
    title: toSourceTitle(source, sourceType),
    content: source.citation_rationale?.trim() || source.text?.trim() || '',
    date: formatSourceDate(source),
    author: source.source === 'jira' ? (source.assignee ?? source.author ?? '') : (source.author ?? ''),
    html_url: source.url ?? '',
    source_index: typeof source.index === 'number' ? source.index : 0,
  };
};

export const MOCK_CHAT_SOURCES: MockChatSource[] = MOCK_SOURCES.map(toChatSource);

export const buildStreamingMockAnswer = (query: string) =>
  [
    `# "${query}"에 대한 Streaming 답변 [3]`,
    '',
    '이 답변은 token 단위로 전송되며, markdown 렌더링이 흔들리지 않아야 합니다 [1].',
    '',
    '## 1. Inline 문법 [4]',
    '- **굵게**',
    '- *기울임*',
    '- ~~취소선~~',
    '- `inline code`',
    '- [repo link](https://github.com/TeamCatchUp/CatchUp-FE) [1]',
    '',
    '## 2. List 예시 [1]',
    '1. 첫 번째 단계',
    '2. 두 번째 단계',
    '3. 세 번째 단계 [3]',
    '',
    '- 순서 없는 항목 A',
    '- 순서 없는 항목 B',
    '- [x] 완료된 작업',
    '- [ ] 남은 작업',
    '',
    '## 3. Quote + 규칙 [3]',
    '> Backend stream 순서: status -> sources -> token -> sources',
    '',
    '---',
    '',
    '## 4. Table [4]',
    '| Event | 설명 |',
    '| --- | --- |',
    '| status | 현재 진행 단계를 표시 |',
    '| sources | sidebar의 후보/최종 출처를 갱신 |',
    '| token | 답변 본문을 실시간으로 누적 |',
    '',
    '## 5. Code 예시 [1]',
    '```ts',
    "type StreamEvent = 'status' | 'sources' | 'token';",
    '',
    'function appendToken(prev: string, token: string) {',
    '  return prev + token;',
    '}',
    '```',
    '',
    '```json',
    '{',
    '  "type": "token",',
    '  "session_id": "demo-session",',
    '  "token": "hello "',
    '}',
    '```',
    '',
    '## 6. Confluence 출처 [6]',
    'RAG 파이프라인 아키텍처는 Confluence 문서에서 확인할 수 있습니다 [6].',
    '',
    '## 7. 마무리 [1][4]',
    '인용된 cited source와 참고용 source는 분리해서 보여줘야 합니다.',
  ].join('\n');

export const MOCK_RAG_ANSWER = buildStreamingMockAnswer('RAG 스트리밍');

export const MOCK_INITIAL_MESSAGES: MockMessage[] = [
  {
    id: 'mock-q1',
    role: 'user',
    content: '이 채팅에서 token streaming은 어떻게 동작하나요?',
    timestamp: '2026-02-12T09:00:00.000Z',
  },
  {
    id: 'mock-a1',
    chat_history_id: 'mock-history-001',
    role: 'assistant',
    content: MOCK_RAG_ANSWER,
    sources: MOCK_CHAT_SOURCES,
    detailed_tasks: [],
    timestamp: '2026-02-12T09:00:05.000Z',
    has_feedback: false,
  },
];

export const MOCK_RELATED_JIRA_ISSUES: MockSource[] = [];
