import type { IntegrationService } from '../types/integrationModel';

export interface ConnectorScopeRow {
  label: string;
  value: string;
}

export interface ConnectorContent {
  name: string;
  category: (typeof CONNECTOR_CATEGORIES)[number];
  /** 카탈로그 카드 한 줄 설명 */
  catalogDescription: string;
  /** 상세 헤더 한 줄 설명 */
  headerDescription: string;
  /** 상세 본문 소개 문단 */
  intro: string;
  sampleQuestions: readonly string[];
  scope: readonly ConnectorScopeRow[];
  included: readonly string[];
  excluded: readonly string[];
  guideLabel: string;
}

/** 카탈로그 카테고리. Figma 16922:134207의 표기와 순서를 그대로 따른다 */
export const CONNECTOR_CATEGORIES = ['커뮤니케이션', '문서 · 지식', '개발 · 이슈 관리'] as const;

/*
 * TODO(copy): Jira · Github · Confluence 의 intro / sampleQuestions / scope /
 * included / excluded 는 Figma에 연동 전 상세 프레임이 없어 Slack 값을 복제했다.
 *
 * 복제한 값에는 Slack 전용 어휘가 있다 — "DM · 그룹 DM", "봇을 초대한 비공개 채널",
 * "스레드 안의 답글". 다른 도구 화면에 그대로 나가면 사실과 다른 데이터 범위 안내가 된다.
 * 배포 전 카피 확정이 필요하다. 스펙 §8 결정 #4 참조.
 *
 * headerDescription 은 도구별로 분리했다(아래 *_HEADER_DESCRIPTION). 헤더는 연동 전·후
 * 양쪽에 노출돼서 Slack 문구가 채널톡 상세에 그대로 찍히는 게 눈에 띄었다.
 */
const SLACK_SCOPE: readonly ConnectorScopeRow[] = [
  { label: '무엇을', value: '메시지 · 스레드 · 답글 (선택한 채널의 대화)' },
  { label: '어디까지', value: '내가 고른 채널만. 공개 채널은 바로, 비공개 채널은 봇을 초대한 뒤' },
  { label: '언제·어떻게', value: '연결 시 과거 대화 1차 동기화 → 이후 새 메시지 자동 반영' },
  { label: '누가 볼 수 있나', value: '워크스페이스 멤버 (원본 채널 공개 범위를 따름)' },
];

const SLACK_SAMPLE_QUESTIONS = [
  '"이번 주에 우리가 뭘 결정했지?"',
  '"답 안 달린 질문들만 모아줘"',
  '"이번 주 논의 요약해줘"',
] as const;

const SLACK_INCLUDED = [
  '선택한 공개 채널의 메시지 · 스레드',
  '봇을 초대한 비공개 채널',
  '스레드 안의 답글 · 맥락',
] as const;

const SLACK_EXCLUDED = [
  'DM · 그룹 DM — 봇은 초대된 채널만 읽어요',
  '초대하지 않은 비공개 채널',
  '선택하지 않은 채널',
] as const;

const SLACK_INTRO =
  '결정, 맥락, 답변이 Slack에선 매일 스크롤 아래로 사라집니다. 중요한 채널만 동기화해두면, 필요할 때 다시 불러올 수 있어요.';

/*
 * 헤더 한 줄 설명. Slack 것만 Figma `16922:134099` 실측값이고, 나머지는 그 문형
 * ("<어디>에 묻힌 <무엇>을 다시 꺼내오세요")을 따라 도구별 어휘로 맞춘 초안이다.
 * 카탈로그 카드의 catalogDescription 과 대상 어휘를 일치시켰다.
 */
const SLACK_HEADER_DESCRIPTION = '채팅 스레드에 묻힌 결정을 다시 꺼내오세요';
const CHANNEL_TALK_HEADER_DESCRIPTION = '상담 이력에 묻힌 답변을 다시 꺼내오세요';
const CONFLUENCE_HEADER_DESCRIPTION = '문서에 묻힌 결정의 근거를 다시 꺼내오세요';
const JIRA_HEADER_DESCRIPTION = '이슈에 묻힌 작업 맥락을 다시 꺼내오세요';
const GITHUB_HEADER_DESCRIPTION = 'PR · 리뷰에 묻힌 논의를 다시 꺼내오세요';

/*
 * 채널톡 카피. Figma에 연동 전 상세 프레임이 없어 초안이다 — 다만 Slack 값을 그대로
 * 두는 것보다는 낫다. Slack 복제본은 "DM · 그룹 DM", "봇을 초대한 비공개 채널"처럼
 * 채널톡에 없는 개념을 데이터 범위 안내로 내보내고 있었다.
 *
 * 채널톡의 연결 단위는 "채널"(고객사 워크스페이스)이고 채널마다 액세스 키 등록이
 * 선행이다 — (F) 채널 연결 관리 스텝이 그것이다. scope / excluded 문구는 그 전제를 따랐다.
 */
const CHANNEL_TALK_SCOPE: readonly ConnectorScopeRow[] = [
  { label: '무엇을', value: '고객 상담 대화 · 매니저 답변 (선택한 채널의 상담 이력)' },
  { label: '어디까지', value: '내가 연결한 채널만. 채널마다 액세스 키를 등록한 뒤' },
  { label: '언제·어떻게', value: '연결 시 지난 상담 1차 동기화 → 이후 새 상담 자동 반영' },
  { label: '누가 볼 수 있나', value: '워크스페이스 멤버 (원본 채널 접근 범위를 따름)' },
];

const CHANNEL_TALK_SAMPLE_QUESTIONS = [
  '"환불 문의는 보통 어떻게 안내했지?"',
  '"이번 주에 가장 많이 들어온 문의가 뭐야?"',
  '"이 오류를 문의한 고객에게 뭐라고 답했지?"',
] as const;

const CHANNEL_TALK_INCLUDED = [
  '연결한 채널의 고객 상담 대화',
  '상담에 달린 매니저 답변 · 후속 대응',
  '상담이 오간 순서와 맥락',
] as const;

const CHANNEL_TALK_EXCLUDED = [
  '팀 채팅 · 매니저 간 DM — 고객 상담만 읽어요',
  '액세스 키를 등록하지 않은 채널',
  '상담에 첨부된 파일의 내용',
] as const;

const CHANNEL_TALK_INTRO =
  '고객이 이미 물어본 것, 우리가 이미 답한 것이 상담 이력 아래로 쌓입니다. 필요한 채널만 동기화해두면 같은 질문에 매번 처음부터 찾지 않아도 돼요.';

/** 커넥터별 카탈로그·상세 문구. Figma 16922:134207 · 16922:134092 실측값 */
export const CONNECTOR_CONTENT: Record<IntegrationService, ConnectorContent> = {
  slack: {
    name: 'Slack',
    category: '커뮤니케이션',
    catalogDescription: '채팅에 흩어진 결정과 답을 다시 찾아요',
    headerDescription: SLACK_HEADER_DESCRIPTION,
    intro: SLACK_INTRO,
    sampleQuestions: SLACK_SAMPLE_QUESTIONS,
    scope: SLACK_SCOPE,
    included: SLACK_INCLUDED,
    excluded: SLACK_EXCLUDED,
    guideLabel: 'Slack 연동 가이드 보기',
  },
  channel_talk: {
    name: '채널톡',
    category: '커뮤니케이션',
    catalogDescription: '상담 이력에서 문의 대응에 필요한 답 찾기',
    headerDescription: CHANNEL_TALK_HEADER_DESCRIPTION,
    intro: CHANNEL_TALK_INTRO,
    sampleQuestions: CHANNEL_TALK_SAMPLE_QUESTIONS,
    scope: CHANNEL_TALK_SCOPE,
    included: CHANNEL_TALK_INCLUDED,
    excluded: CHANNEL_TALK_EXCLUDED,
    guideLabel: '채널톡 연동 가이드 보기',
  },
  confluence: {
    name: 'Confluence',
    category: '문서 · 지식',
    catalogDescription: '위키·기획 문서에서 근거와 함께 답 찾기',
    headerDescription: CONFLUENCE_HEADER_DESCRIPTION,
    intro: SLACK_INTRO, // TODO(copy)
    sampleQuestions: SLACK_SAMPLE_QUESTIONS, // TODO(copy)
    scope: SLACK_SCOPE, // TODO(copy)
    included: SLACK_INCLUDED, // TODO(copy)
    excluded: SLACK_EXCLUDED, // TODO(copy)
    guideLabel: 'Confluence 연동 가이드 보기',
  },
  jira: {
    name: 'Jira',
    category: '개발 · 이슈 관리',
    catalogDescription: '이슈에 흩어진 작업 맥락과 결정의 이유 찾기',
    headerDescription: JIRA_HEADER_DESCRIPTION,
    intro: SLACK_INTRO, // TODO(copy)
    sampleQuestions: SLACK_SAMPLE_QUESTIONS, // TODO(copy)
    scope: SLACK_SCOPE, // TODO(copy)
    included: SLACK_INCLUDED, // TODO(copy)
    excluded: SLACK_EXCLUDED, // TODO(copy)
    guideLabel: 'Jira 연동 가이드 보기',
  },
  github: {
    name: 'Github',
    category: '개발 · 이슈 관리',
    catalogDescription: 'PR·이슈·코드에 숨은 맥락까지 검색',
    headerDescription: GITHUB_HEADER_DESCRIPTION,
    intro: SLACK_INTRO, // TODO(copy)
    sampleQuestions: SLACK_SAMPLE_QUESTIONS, // TODO(copy)
    scope: SLACK_SCOPE, // TODO(copy)
    included: SLACK_INCLUDED, // TODO(copy)
    excluded: SLACK_EXCLUDED, // TODO(copy)
    guideLabel: 'Github 연동 가이드 보기',
  },
};
