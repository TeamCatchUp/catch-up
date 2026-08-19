/**
 * LLM Wiki 온보딩 mock. 2026-08-14 시안 갱신으로 카피 대부분이 실카피로 확정됐다.
 * "text text" 필러가 남은 2곳(템플릿 예시 본문·채널 표 행)만 카피 미정(TBD)이다.
 */
import type {
  OnboardingChannelRow,
  OnboardingStepInfo,
  OnboardingSummarySection,
  ScheduleFieldData,
  WikiDocKindPreset,
  WikiInfoCategory,
  WikiPurposeOption,
  WikiToneStyleOption,
} from '../types/llmWikiOnboarding';

export const ONBOARDING_STEPS: readonly OnboardingStepInfo[] = [
  { number: 1, label: '위키의 목적 설정' },
  { number: 2, label: '수집 위치 설정' },
  { number: 3, label: '확인 및 완료' },
];

export const ONBOARDING_PURPOSE_HEADING = '이 위키는 무엇을 위한 위키인가요?';
export const ONBOARDING_SOURCE_HEADING = '수집 위치를 설정해 주세요';
export const ONBOARDING_COMPLETE_HEADING = '설정이 거의 다 완료됐어요!';
export const ONBOARDING_BASIC_INFO_TITLE = '기본 위키 정보';
export const ONBOARDING_DOC_SETTING_TITLE = '문서 설정';

// [BE] 이름은 1~20자다(POST /wiki/channels/onboarding) — 상한은 입력에서 막는다
export const WIKI_NAME_FIELD = {
  label: '이름',
  placeholder: 'CS 응답, 제품 용어 사전',
  maxLength: 20,
} as const;

export const INFO_CATEGORY_FIELD_LABEL = '어떤 정보를 정리하고 싶으세요?';
export const PURPOSE_FIELD_LABEL = '이 위키를 어떻게 쓰실 건가요?';

// VOC만 지원한다 — 나머지는 앞으로 열릴 자리라 고를 수 없이 노출된다
export const WIKI_INFO_CATEGORIES: readonly WikiInfoCategory[] = [
  { id: 'voc', label: '고객 문의 (VOC)', icon: 'support-agent' },
  { id: 'product', label: '제품과 기획', icon: 'lightbulb', disabled: true },
  { id: 'ops', label: '운영과 정책', icon: 'shield', disabled: true },
  { id: 'sales', label: '세일즈와 고객', icon: 'client', disabled: true },
  { id: 'dev', label: '개발과 기술', icon: 'database', disabled: true },
  { id: 'team-guide', label: '팀 가이드 및 온보딩', icon: 'group', disabled: true },
];

/**
 * 목적 선택지. 시안은 VOC를 고른 상태만 그렸지만 카테고리별로 갈린다는 근거가 없어
 * 어느 칩을 골라도 같은 목록이 이어진다(8/14 사용자 확정).
 */
export const WIKI_PURPOSE_OPTIONS: readonly WikiPurposeOption[] = [
  { id: 'feature-demand', label: '어떤 기능을 가장 많이 요청하는지 모아보고 싶어요' },
  { id: 'faq', label: '자주 들어오는 질문과 답변을 정리해두고 싶어요' },
  { id: 'pain-point', label: '고객이 어디서 자주 불편해하는지 모아보고 싶어요' },
  { id: 'client-request', label: '고객사별로 지금까지 나온 요청과 맥락을 보고 싶어요' },
  { id: 'customer-needs', label: '상담에서 반복해서 보이는 고객 니즈를 모으고 싶어요' },
];

export const DOC_KIND_FIELD_LABEL = '어떤 종류의 문서를 만들까요?';
export const DOC_KIND_SAMPLE_TITLE = '템플릿 예시';
/** 목적이 수집 범위가 아니라 문서 종류·문체에만 쓰인다는 오해 방지 카피 */
export const DOC_KIND_SAMPLE_CAPTION = '입력한 목적은 만들 문서의 종류와 문체를 정하는 데 쓰여요.';

// 기능 요청 정리만 지원한다 — 나머지는 앞으로 열릴 자리라 고를 수 없이 노출된다
export const WIKI_DOC_KIND_PRESETS: readonly WikiDocKindPreset[] = [
  {
    id: 'feature-request',
    icon: 'request',
    label: '기능 요청 정리',
    description: '고객이 원하는 기능과 그 이유, 사용 상황을 정리한 문서',
  },
  {
    id: 'pain-point',
    icon: 'error',
    label: '고객 불편사항 정리',
    description: '고객이 어떤 상황에서 불편을 겪는지 정리한 문서',
    disabled: true,
  },
  {
    id: 'faq',
    icon: 'help',
    label: '자주 묻는 질문 정리',
    description: '반복되는 질문과 현재 기준 답변을 정리한 문서',
    disabled: true,
  },
  {
    id: 'client-request',
    icon: 'client',
    label: '고객사별 요청사항 정리',
    description: '특정 고객사가 요청한 기능과 조건을 정리한 문서',
    disabled: true,
  },
  {
    id: 'client-history',
    icon: 'history',
    label: '고객사 히스토리 정리',
    description: '고객사와 오간 문의·요청·결정을 시간순으로 정리한 문서',
    disabled: true,
  },
  {
    id: 'policy',
    icon: 'book',
    label: '정책 · 예외사항 정리',
    description: '현재 적용 기준과 예외로 처리되는 경우를 정리한 문서',
    disabled: true,
  },
];

// 앞 문장만 실카피, 뒤는 시안 필러 그대로 — 발행본에는 처리 상태값을 남기지 않는다
export const TEMPLATE_SAMPLE_TEXT_TBD =
  '엑셀 내보내기 기능 요청. 5개 고객사에서 반복 접수됐다. text text text text text text text text text text text text text text text text text text text text text text text text text text text text text text';

export const TONE_STYLE_FIELD_LABEL = '문서를 어떤 문체로 쓸까요?';
export const TONE_SAMPLE_TAG_LABEL = '예시';

export const WIKI_TONE_STYLE_OPTIONS: readonly WikiToneStyleOption[] = [
  {
    id: 'wiki-standard',
    label: '위키 표준체',
    description: '중립 서술체로 사실과 근거, 시점을 건조하게 기록',
    sampleText: '엑셀 내보내기 기능에 대한 요구. 5개 고객사에서 반복 접수됐다.',
  },
  {
    id: 'support-guide',
    label: '응대 가이드체',
    description: '고객에게 그대로 전달할 수 있는 해요체 표현',
    sampleText: '엑셀 내보내기는 아직 지원하지 않아요. 현재 지원 범위를 그대로 안내해 주세요.',
  },
  {
    id: 'report-summary',
    label: '보고 요약체',
    description: '두괄식 요약과 수치로 판단에 필요한 규모를 앞세움',
    sampleText: '엑셀 내보내기 요구 누적 5개사. 최근 한 달 접수 증가.',
  },
];

export const CHANNEL_FIELD_LABEL = '어떤 채널톡 채널의 문의를 감지할까요?';
/** 명세의 수집 범위 오해 방지 카피 */
export const CHANNEL_FIELD_CAPTION = '선택한 채널의 고객 상담만 읽어요. 팀챗 등 내부 대화는 읽지 않아요.';
export const CHANNEL_PICKER_PLACEHOLDER = '채널톡 내 채널을 선택해주세요';
export const CHANNEL_TABLE_HEADERS = { name: '채널명', lastModified: '최근 수정일' } as const;

// 행 카피는 시안 필러(TBD). 채널은 채널톡 자격증명 계약 모양을 지킨다 — 수정일만 [SPEC]
export const ONBOARDING_CHANNEL_ROWS: readonly OnboardingChannelRow[] = Array.from({ length: 5 }, (_, index) => ({
  channel: {
    credentialId: index + 1,
    name: '채널명 text text text text text text text text text text text text text',
    externalId: `ct-channel-${index + 1}`,
    isConfigured: true,
  },
  lastModifiedLabel: '2025.01.23',
}));

/**
 * 기본값과 주기 선택지는 기획 문서(Confluence 160301060 §3.2)가 원천이다 —
 * 시안 트리거의 "1분"은 공용 컴포넌트 필러였고 완료 화면 요약("매일"·"자정")이 기획과 일치한다.
 */
export const SCHEDULE_FIELDS: readonly ScheduleFieldData[] = [
  {
    id: 'polling-interval',
    label: '얼마나 자주 갱신할까요?',
    valueLabel: '매일',
    icon: 'calendar-clock',
    options: [
      { id: '6h', label: '6시간마다' },
      { id: '12h', label: '12시간마다' },
      { id: 'daily', label: '매일' },
      { id: 'weekly', label: '주 1회' },
    ],
  },
  {
    id: 'backfill-range',
    label: '언제부터의 상담을 가져올까요?',
    valueLabel: '지금부터',
    // 앞 둘은 추후 지원이라 고를 수 없이 노출된다(기획 §3.2, 시안 disabled)
    options: [
      { id: 'all', label: '전체 이력', disabled: true },
      { id: 'recent-months', label: '최근 N개월', disabled: true },
      { id: 'from-now', label: '지금부터' },
    ],
  },
  {
    id: 'run-time',
    label: '몇 시에 실행할까요?',
    valueLabel: '자정',
    options: [
      { id: 'midnight', label: '자정' },
      { id: '6am', label: '오전 6시' },
      { id: 'noon', label: '정오' },
      { id: '6pm', label: '오후 6시' },
    ],
  },
];

/**
 * 일정 필드의 기본 선택. 트리거에 그려진 값이 곧 초기값이라 라벨로 역산한다 —
 * 보이는 값과 상태가 어긋나면 사용자가 고르지 않은 설정을 고른 줄 안다.
 */
export const INITIAL_SCHEDULE_SELECTION: Readonly<Record<string, string>> = Object.fromEntries(
  SCHEDULE_FIELDS.flatMap((field) => {
    const picked = field.options?.find((option) => option.label === field.valueLabel);
    return picked ? [[field.id, picked.id] as const] : [];
  }),
);

export const SCHEDULE_RESULT_TEXT = '매일 자정에 새 상담을 확인하고 문서 초안을 만들어요.';
export const BACKFILL_NOTICE_TEXT = '과거 이력 가져오기는 곧 지원돼요.';

export const ONBOARDING_NEXT_LABEL = '다음 단계로';
export const ONBOARDING_BACK_LABEL = '이전';
export const ONBOARDING_FINISH_LABEL = '완료하기';

/** 완료 화면 요약. 값은 시안 실측이고, 1단계 선택분은 라우트가 실제 입력으로 덮어쓴다 */
export const ONBOARDING_SUMMARY_SECTIONS: readonly OnboardingSummarySection[] = [
  {
    title: '위키 목적',
    rows: [
      { label: '이름', values: ['CS 응대 위키'] },
      { label: '정리할 정보', values: ['고객 문의 (VOC)'] },
      { label: '목적', values: ['어떤 기능을 가장 많이 요청하는지 모아보고 싶어요'] },
      // 시안 요약은 1단계 프리셋 라벨의 축약형("기능 요청 정리"→"기능 요청")이다 — 시안 그대로 둔다
      { label: '문서 종류', values: ['기능 요청', '자주 묻는 질문', '고객사별 요청'], variant: 'badge' },
      { label: '문체', values: ['위키 표준체'] },
    ],
  },
  {
    title: '수집 설정',
    rows: [
      { label: '갱신 주기', values: ['매일'] },
      { label: '언제부터', values: ['지금부터'] },
      { label: '실행시간', values: ['자정'] },
    ],
  },
];

/** 요약의 채널은 행이 아니라 2단계와 같은 표로 놓인다 */
export const ONBOARDING_SUMMARY_CHANNEL_LABEL = '연결한 채널톡 채널';

export const ONBOARDING_NEXT_STEPS_TITLE = '위키를 만들면';

/** 명세의 완료 화면 3요소 — ①② 시간 약속, ③ 검수 안내. 별도 철학 문단은 시안에 없다 */
export const ONBOARDING_NEXT_STEPS: readonly string[] = [
  '오늘 들어오는 상담부터 수집을 시작해요',
  '내일 자정 첫 갱신 때 첫 문서 초안이 검토 큐에 도착해요',
  '문서는 사람의 승인 없이는 바뀌지 않아요',
];
