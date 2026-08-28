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
 * Jira · Confluence · Github · 채널톡 카피는 Confluence "커넥터 연동 안내 문구"
 * (CU 스페이스, pageId 157941761, 2026-08-04 판)를 원문 그대로 옮겼다.
 * Slack만 그 문서에 없어 Figma `16922:134092` 실측값을 유지한다.
 *
 * 원문과 다르게 적용한 것 두 가지뿐이다:
 *   - scope 라벨 "언제, 어떻게" → "언제·어떻게" (Slack Figma 라벨 표기를 따름)
 *   - 예시 질문은 기존 렌더 형식대로 따옴표로 감싼다
 *
 * headerDescription 은 문서에 없다 — 도구별 초안(아래 *_HEADER_DESCRIPTION)을 유지한다.
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
 * 헤더 한 줄 설명. Slack 것만 Figma `16922:134099` 실측값이고 나머지는 초안이다.
 *
 * 일부러 같은 문형을 돌려쓰지 않았다 — 도구를 옮겨다니며 볼 때 문장 틀만 같고 명사만
 * 갈리면 카피가 아니라 템플릿으로 읽힌다. 대신 각 도구가 실제로 되찾아주는 것을
 * 다르게 잡았다: 채널톡은 지난 답변, Confluence는 출처, Jira는 결정의 이유,
 * Github은 코드 밖 논의.
 *
 * 헤더는 truncate 되므로 Slack 원본(22자) 언저리를 넘기지 않는다.
 */
const SLACK_HEADER_DESCRIPTION = '채팅 스레드에 묻힌 결정을 다시 꺼내오세요';
const CHANNEL_TALK_HEADER_DESCRIPTION = '고객이 물어본 것, 우리가 답한 것 그대로 찾아드려요';
const CONFLUENCE_HEADER_DESCRIPTION = '어느 문서에 있었는지까지 같이 알려드려요';
const JIRA_HEADER_DESCRIPTION = '왜 이렇게 하기로 했는지, 이슈가 기억하고 있어요';
const GITHUB_HEADER_DESCRIPTION = 'PR과 리뷰에 오간 이야기까지 검색됩니다';

// ─── Jira ───

const JIRA_INTRO =
  '완료된 이슈는 누구도 다시 열어보지 않아요. 하지만 왜 그렇게 결정했고 어떻게 해결했는지는 전부 그 안에 남아 있죠. 프로젝트를 동기화해두면, 필요할 때 다시 불러올 수 있어요.';

const JIRA_SAMPLE_QUESTIONS = [
  '"이 기능 왜 보류됐었지?"',
  '"그 버그, 전에도 리포트된 적 있어?"',
  '"지난 스프린트에서 안 끝난 이슈 뭐야?"',
] as const;

const JIRA_SCOPE: readonly ConnectorScopeRow[] = [
  { label: '무엇을', value: '이슈, 댓글, 상태 변경 이력 (선택한 프로젝트의 작업 기록)' },
  { label: '어디까지', value: '내가 고른 프로젝트만. 연동 계정에 접근 권한이 있는 프로젝트만 선택할 수 있어요' },
  { label: '언제·어떻게', value: '연결 시 기존 이슈 1차 동기화 → 이후 새 이슈와 변경 사항 자동 반영' },
  { label: '누가 볼 수 있나', value: '워크스페이스 멤버 (원본 프로젝트의 접근 권한을 따름)' },
];

const JIRA_INCLUDED = [
  '선택한 프로젝트의 이슈와 댓글',
  '이슈의 상태와 담당자 변경 이력',
  '에픽–하위 이슈의 연결 관계',
  '스프린트와 백로그의 작업 목록',
] as const;

const JIRA_EXCLUDED = [
  '선택하지 않은 프로젝트',
  '연동 계정에 접근 권한이 없는 프로젝트',
  '첨부파일 원본 — 이슈 본문과 댓글의 텍스트를 읽어요',
  '개인 필터와 보드 설정',
] as const;

// ─── Confluence ───

const CONFLUENCE_INTRO =
  '문서는 계속 쌓이는데, 어떤 게 최신이고 어디에 있는지는 아무도 정확히 모릅니다. 정리한 사람이 떠나면 지식도 함께 사라져요. 컨플루언스 스페이스를 동기화해두면, 필요할 때 다시 불러올 수 있어요.';

const CONFLUENCE_SAMPLE_QUESTIONS = [
  '"온보딩 가이드 최신 버전 어디 있어?"',
  '"이 정책, 언제 어떻게 바뀌었지?"',
  '"그때 회의록에서 결정 근거 찾아줘"',
] as const;

const CONFLUENCE_SCOPE: readonly ConnectorScopeRow[] = [
  { label: '무엇을', value: '페이지, 댓글, 페이지 계층 구조 (선택한 스페이스의 문서)' },
  { label: '어디까지', value: '내가 고른 스페이스만. 열람 제한이 걸린 페이지는 연동 계정의 권한을 따라요' },
  { label: '언제·어떻게', value: '연결 시 기존 페이지 1차 동기화 → 이후 수정되거나 새로 만든 페이지 자동 반영' },
  { label: '누가 볼 수 있나', value: '워크스페이스 멤버 (원본 스페이스의 공개 범위를 따름)' },
];

const CONFLUENCE_INCLUDED = [
  '선택한 스페이스의 페이지와 하위 페이지',
  '발행된 페이지, 초안(Draft), 휴지통 페이지',
  '페이지에 달린 댓글',
  '페이지 간 계층과 링크 관계',
] as const;

const CONFLUENCE_EXCLUDED = [
  '선택하지 않은 스페이스',
  '첨부파일 원본 — 페이지 본문과 댓글의 텍스트를 읽어요',
  '열람 제한으로 연동 계정이 볼 수 없는 페이지',
  '페이지 작성과 수정 — 읽기 전용으로 동작해요',
] as const;

// ─── Github ───

const GITHUB_INTRO =
  '코드에는 "왜"가 없습니다. 왜 이렇게 구현했는지는 PR 리뷰와 이슈 논의에 있는데, 머지되는 순간 아무도 다시 읽지 않아요. 중요한 리포지토리만 동기화해두면, 필요할 때 다시 불러올 수 있어요.';

const GITHUB_SAMPLE_QUESTIONS = [
  '"이 로직, 왜 이렇게 바꿨었지?"',
  '"그 버그 어떤 PR에서 고쳤어?"',
  '"이 모듈 최근에 어떤 변경이 있었어?"',
] as const;

const GITHUB_SCOPE: readonly ConnectorScopeRow[] = [
  { label: '무엇을', value: '이슈, PR, 리뷰 코멘트 (선택한 리포지토리의 개발 기록)' },
  { label: '어디까지', value: '내가 고른 리포지토리만. 프라이빗 리포는 앱 설치 시 접근을 허용한 것만' },
  { label: '언제·어떻게', value: '연결 시 기존 이슈와 PR 1차 동기화 → 이후 새 활동 자동 반영' },
  { label: '누가 볼 수 있나', value: '워크스페이스 멤버 (원본 리포지토리의 접근 권한을 따름)' },
];

const GITHUB_INCLUDED = [
  '선택한 리포의 이슈, PR, 리뷰 코멘트',
  'PR의 변경 요약과 커밋 메시지',
  '접근을 허용한 프라이빗 리포',
  '이슈와 PR의 라벨, 상태 이력',
] as const;

const GITHUB_EXCLUDED = [
  '선택하지 않은 리포지토리',
  '접근을 허용하지 않은 프라이빗 리포',
  '코드 수정과 푸시 — 읽기 전용으로만 동작해요',
] as const;

// ─── 채널톡 ───

const CHANNEL_TALK_INTRO =
  '상담은 종료돼도 고객의 목소리는 반복됩니다. 같은 질문, 같은 요구가 매일 새 상담으로 다시 들어와요. 상담을 동기화해두면, 흩어진 문의를 고객별, 주제별로 다시 불러올 수 있어요.';

const CHANNEL_TALK_SAMPLE_QUESTIONS = [
  '"이 고객사, 전에 뭐 문의했었지?"',
  '"이번 주 가장 많이 들어온 문의 뭐야?"',
  '"이 기능 요청한 고객이 어디어디야?"',
] as const;

const CHANNEL_TALK_SCOPE: readonly ConnectorScopeRow[] = [
  { label: '무엇을', value: '고객 상담 대화와 상담 태그 (연결한 채널의 상담 기록)' },
  { label: '어디까지', value: '연결한 채널톡 채널만. 고객 상담 대화를 읽어요 — 팀챗 등 내부 대화는 읽지 않아요' },
  { label: '언제·어떻게', value: '연결 시 과거 상담 1차 동기화 → 이후 새 상담 자동 반영' },
  // 원문 그대로다 — "위키 권한 설정"이 CatchUp 어휘와 맞는지는 문서 쪽에 확인 필요
  { label: '누가 볼 수 있나', value: '워크스페이스 멤버 (위키 권한 설정을 따름)' },
];

const CHANNEL_TALK_INCLUDED = [
  '상담 대화 내용 — 진행 중이거나 종료된 상담 모두',
  '연결 시점 이전의 과거 상담',
  '고객사별 문의 이력 타임라인과 상담 태그',
  '문의에서 이어지는 요구, 버그 신호',
] as const;

const CHANNEL_TALK_EXCLUDED = ['팀챗 등 내부 대화 — 고객과의 상담만 읽어요'] as const;

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
    intro: CONFLUENCE_INTRO,
    sampleQuestions: CONFLUENCE_SAMPLE_QUESTIONS,
    scope: CONFLUENCE_SCOPE,
    included: CONFLUENCE_INCLUDED,
    excluded: CONFLUENCE_EXCLUDED,
    guideLabel: 'Confluence 연동 가이드 보기',
  },
  jira: {
    name: 'Jira',
    category: '개발 · 이슈 관리',
    catalogDescription: '이슈에 흩어진 작업 맥락과 결정의 이유 찾기',
    headerDescription: JIRA_HEADER_DESCRIPTION,
    intro: JIRA_INTRO,
    sampleQuestions: JIRA_SAMPLE_QUESTIONS,
    scope: JIRA_SCOPE,
    included: JIRA_INCLUDED,
    excluded: JIRA_EXCLUDED,
    guideLabel: 'Jira 연동 가이드 보기',
  },
  github: {
    name: 'Github',
    category: '개발 · 이슈 관리',
    catalogDescription: 'PR·이슈·코드에 숨은 맥락까지 검색',
    headerDescription: GITHUB_HEADER_DESCRIPTION,
    intro: GITHUB_INTRO,
    sampleQuestions: GITHUB_SAMPLE_QUESTIONS,
    scope: GITHUB_SCOPE,
    included: GITHUB_INCLUDED,
    excluded: GITHUB_EXCLUDED,
    guideLabel: 'Github 연동 가이드 보기',
  },
};
