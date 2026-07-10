import type { ChatSource, Message, PipelineEvent } from '@/features/chat/types';
import type { QAPair } from '@/features/chat/utils/render/chat';

export type ChatSourcePreset = 'jira' | 'github' | 'slack' | 'confluence' | 'channel-talk-chat' | 'channel-talk-doc';

export const chatStorySessionId = 'storybook-chat-session';
export const chatStoryMessageId = 'storybook-answer-message';
export const chatStoryHistoryId = '4242';

export const chatSourcePresetOptions: readonly ChatSourcePreset[] = [
  'jira',
  'github',
  'slack',
  'confluence',
  'channel-talk-chat',
  'channel-talk-doc',
];

export const chatSourceFixtures = {
  jira: {
    id: 'chat-source-jira-248',
    source_type: 'jira',
    entity_type: 'issue',
    is_cited: true,
    repo: 'CatchUp Product',
    title: '결제 승인 실패 시 재시도 정책 정리',
    content: '승인 실패 유형별 재시도 간격과 운영자 알림 조건을 정의합니다.',
    date: '2026. 07. 08.',
    author: 'Product Ops',
    html_url: 'https://example.com/jira/CU-248',
    source_index: 3,
    issue_key: 'CU-248',
  },
  github: {
    id: 'chat-source-github-132',
    source_type: 'github',
    entity_type: 'pr',
    is_cited: false,
    repo: 'catchup/frontend',
    title: '답변 출처 사이드바 필터 상태 정리',
    content: '출처 플랫폼 필터와 인용 순서를 일관되게 표시하는 변경입니다.',
    date: '2026. 07. 07.',
    author: 'frontend-bot',
    html_url: 'https://example.com/github/catchup/frontend/pull/132',
    source_index: 2,
    github_number: 132,
  },
  slack: {
    id: 'chat-source-slack-search',
    source_type: 'slack',
    entity_type: 'message',
    is_cited: true,
    repo: '#product-search',
    title: '재시도는 승인 실패 코드가 일시 오류인 경우에만 허용하기로 했습니다.',
    content: '영구 실패 코드는 즉시 고객 안내로 전환하고 운영 채널에 알립니다.',
    date: '2026. 07. 09.',
    author: '이서연',
    html_url: 'https://example.com/slack/archives/C123/p1713600000000000',
    source_index: 1,
  },
  confluence: {
    id: 'chat-source-confluence-runbook',
    source_type: 'confluence',
    entity_type: 'page',
    is_cited: true,
    repo: 'Payment Runbook',
    title: '정기 결제 장애 대응 가이드',
    content: '카드사 장애 감지부터 고객 공지, 재처리까지의 대응 순서를 설명합니다.',
    date: '2026. 07. 03.',
    author: 'Platform Squad',
    html_url: 'https://example.com/confluence/payment-runbook',
    source_index: 5,
  },
  'channel-talk-chat': {
    id: 'chat-source-channel-talk-chat',
    source_type: 'channel_talk',
    entity_type: 'user_chat',
    is_cited: false,
    repo: '결제 문의',
    title: '결제 실패 후 다시 시도해도 되는지 알고 싶어요.',
    content: '고객이 결제 실패 알림을 받은 뒤 재시도 가능 시점을 문의한 상담입니다.',
    date: '2026. 07. 09.',
    author: '고객지원팀',
    html_url: 'https://example.com/channel-talk/chats/payment-retry',
    source_index: 4,
  },
  'channel-talk-doc': {
    id: 'chat-source-channel-talk-doc',
    source_type: 'channel_talk',
    entity_type: 'document_article',
    is_cited: false,
    repo: '고객지원 센터',
    title: '결제 승인 실패 안내',
    content: '승인 실패 원인과 고객이 직접 확인할 수 있는 조치 방법을 안내합니다.',
    date: '2026. 07. 06.',
    author: 'Support Team',
    html_url: 'https://example.com/channel-talk/articles/payment-fail',
    source_index: 6,
  },
} satisfies Record<ChatSourcePreset, ChatSource>;

export const chatSourceListFixture: ChatSource[] = chatSourcePresetOptions.map((preset) => chatSourceFixtures[preset]);

export const chatAnswerWithCitations = `### 재시도 기준

일시적인 승인 실패는 운영 정책에 따라 재시도할 수 있습니다.[3] 팀 합의에서는 일시 오류 코드만 재시도 대상으로 제한했습니다.[1]

| 실패 유형 | 처리 방식 |
| --- | --- |
| 일시 오류 | 지수 백오프로 최대 3회 재시도 |
| 영구 오류 | 즉시 고객 안내 후 재시도 중단 |

장애 대응 순서는 런북을 함께 확인하세요.[5]`;

export const complexPipelineEvents: PipelineEvent[] = [
  { node: 'supervisor', status: 'completed', reasoning: '복합 분석이 필요한 질문으로 분류했습니다.' },
  { node: 'rewrite', status: 'completed', content: { query: '결제 승인 실패 재시도 정책과 장애 대응 절차' } },
  { node: 'complex_planner', status: 'in_progress', reasoning: '정책과 운영 대응 순서로 나누어 찾았습니다.' },
  { node: 'complex_planner', status: 'completed', content: { step: 1, intent: '재시도 허용 조건 확인' } },
  { node: 'complex_planner', status: 'completed', content: { step: 2, intent: '장애 대응 런북 확인' } },
  { node: 'tool_executor', status: 'completed', reasoning: '18건의 문서를 찾았습니다.' },
  { node: 'tool_executor', status: 'completed', reasoning: '7건의 대화를 찾았습니다.' },
  { node: 'generate_final_answer', status: 'completed', reasoning: null, content: null },
];

export const chatQuestionFixture: Message = {
  id: 'storybook-question-message',
  role: 'user',
  content: '결제 승인 실패가 발생했을 때 어떤 조건으로 재시도해야 하나요?',
  timestamp: '2026-07-10T09:00:00.000Z',
};

export const chatAnswerFixture: Message = {
  id: chatStoryMessageId,
  chat_history_id: chatStoryHistoryId,
  role: 'assistant',
  content: chatAnswerWithCitations,
  sources: chatSourceListFixture,
  timestamp: '2026-07-10T09:00:08.000Z',
  has_feedback: false,
  is_saved: false,
  pipeline_result: complexPipelineEvents,
};

export function makeChatQAPair(answerOverrides: Partial<Message> = {}): QAPair {
  return {
    question: chatQuestionFixture,
    answer: { ...chatAnswerFixture, ...answerOverrides },
    index: 0,
  };
}
