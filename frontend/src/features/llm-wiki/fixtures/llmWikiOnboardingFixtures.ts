/**
 * LLM Wiki 온보딩 mock. 실카피는 시안 실측이고, "text text" 필러는 카피 미정(TBD)이라
 * 임의 작문 없이 시안 그대로 둔다. 채널 mock은 ChannelListItemResponse 필드를 따른다.
 */
import type {
  OnboardingChannelRow,
  OnboardingStepInfo,
  ScheduleFieldData,
  WikiDocKindPreset,
  WikiPurposeOption,
  WikiToneStyleOption,
} from '../types/llmWikiOnboarding';

export const ONBOARDING_STEPS: readonly OnboardingStepInfo[] = [
  { number: 1, label: '위키의 목적 설정' },
  { number: 2, label: '수집 위치 설정' },
  { number: 3, label: '완료' },
];

export const ONBOARDING_PURPOSE_HEADING = '무엇을 위한 위키인가요?';
export const ONBOARDING_SOURCE_HEADING = '수집 위치를 설정해 주세요';

export const WIKI_NAME_FIELD = {
  label: '이름',
  placeholder: 'CS 응답 위키, 제품 용어 사전',
  maxLength: 20,
} as const;

export const PURPOSE_FIELD_LABEL = '목적';
/** 명세의 오해 방지 카피 — 목적은 수집 범위에 영향을 주지 않는다 */
export const PURPOSE_FIELD_CAPTION = '입력한 목적은 만들 문서의 종류와 문체를 정하는 데 쓰여요';

export const WIKI_PURPOSE_OPTIONS: readonly WikiPurposeOption[] = [
  {
    id: 'new-hire',
    label: '신규 입사자가 제품 용어와 팀 구조를 빨리 익히게',
    followUpQuestion: '주로 어떤 업무를 맡고 있나요?',
  },
  {
    id: 'voc-accumulate',
    label: '고객 문의에서 반복되는 요구를 문서로 축적',
    followUpQuestion: '어떤 문의를 자주 받나요?',
  },
  {
    id: 'decision-trace',
    label: '흩어진 의사결정 배경을 나중에 찾을 수 있게',
    followUpQuestion: '어떤 결정을 남기고 싶나요?',
  },
  // 후속 질문 미도시 — 감사 UNKNOWN, 발명하지 않는다
  { id: 'custom', label: '커스텀 작성하기', followUpQuestion: null },
];

// 시안 입력칸이 필러라 placeholder 카피 미정
export const FOLLOW_UP_PLACEHOLDER_TBD =
  'text text text text text text text text text text text text text text text text text text text text text text text text text';
export const FOLLOW_UP_EXAMPLE =
  '예) iOS 앱 성능 최적화와 배포 파이프라인을 주로 담당해요 / B2B 영업 제안서 작성과 고객사 기술 미팅 대응이 많아요';
export const FOLLOW_UP_MAX_LENGTH = 500;

export const DOC_KIND_FIELD_LABEL = '어떤 종류의 문서를 만들까요?';
export const DOC_KIND_SAMPLE_TITLE = '예시 문장';

export const WIKI_DOC_KIND_PRESETS: readonly WikiDocKindPreset[] = [
  {
    id: 'glossary',
    icon: 'file',
    label: '용어집',
    description: '중립 서술체. 사실, 근거, 시점 중심으로 건조하게 기록',
    // 앞 문장만 실카피, 뒷부분은 시안 필러(TBD)
    sampleText:
      '엑셀 내보내기 기능에 대한 요구. 5개 고객사에서 반복 접수되었으며 현재 상태는 검토 중이다. text text text text text text text text text text text text text text text text text text text text',
  },
  {
    id: 'team-people',
    icon: 'group',
    label: '팀 / 인물',
    description: '고객에게 그대로 전달할 수 있는 표현 중심. 해요체, 현재 안내 가능한 답과 주의점을 앞세움',
    sampleText: 'text text text text text text text text text text text text text text text text',
  },
  {
    id: 'service-overview',
    icon: 'graph',
    label: '서비스 개요',
    description: '두괄식 요약과 수치 중심. 판단에 필요한 규모와 추이를 앞세움',
    sampleText: 'text text text text text text text text text text text text text text text text',
  },
  {
    // 라벨·설명 모두 시안 그대로 — 설명이 서비스 개요와 동일(카피 미정 신호, design-request 참조)
    id: 'decision-history',
    icon: 'search-file',
    label: '의사결정 이력',
    description: '두괄식 요약과 수치 중심. 판단에 필요한 규모와 추이를 앞세움',
    sampleText: 'text text text text text text text text text text text text text text text text',
  },
];

export const TONE_STYLE_FIELD_LABEL = '문서를 어떤 문체로 쓸까요?';

export const WIKI_TONE_STYLE_OPTIONS: readonly WikiToneStyleOption[] = [
  { id: 'wiki-standard', label: '위키 표준체 (기본)' },
  { id: 'support-guide', label: '응대 가이드체' },
  { id: 'report-summary', label: '보고 요약체' },
  // 시안 그대로 — 문서 종류 항목명과 중복(카피 미정 신호, design-request 참조)
  { id: 'decision-history-tone', label: '의사결정 이력' },
];

export const TONE_CUSTOM_OPTION = {
  label: '커스텀 작성하기',
  // 시안 그대로 — 프리셋 설명과 동일한 복붙 필러로 추정(카피 미정)
  description: '두괄식 요약과 수치 중심. 판단에 필요한 규모와 추이를 앞세움',
} as const;

export const TONE_CUSTOM_MAX_LENGTH = 500;

export const CHANNEL_FIELD_LABEL = '어떤 채널로 들어오는 문의를 감지할까요?';
/** 명세의 수집 범위 오해 방지 카피 */
export const CHANNEL_FIELD_CAPTION = '선택한 채널의 고객 상담만 읽어요. 팀챗 등 내부 대화는 읽지 않아요.';
export const CHANNEL_PICKER_PLACEHOLDER = '채널톡 내 채널을 선택해주세요';
export const CHANNEL_TABLE_HEADERS = { name: '채널명', lastModified: '최근 수정일' } as const;

// 행 카피는 시안 필러(TBD). 채널 필드는 백엔드 계약 모양을 지킨다 — 수정일만 [SPEC] 분리
export const ONBOARDING_CHANNEL_ROWS: readonly OnboardingChannelRow[] = [
  '채널명 text text text text text text text text text text text text text',
  '채널명 text text text text text text text text text text text text text',
  '채널명 text text text text text text text text text text text text text',
  '채널명 text text text text text text text text text text text text text',
  '채널명 text text text text text text text text text text text text text',
].map((name, index) => ({
  channel: {
    id: `channel-${index + 1}`,
    name,
    workspaceId: 1,
    isAdmin: index === 0,
    documentCount: index * 3,
    folders: [],
  },
  lastModifiedLabel: '2025-01-23',
}));

export const SCHEDULE_FIELDS: readonly ScheduleFieldData[] = [
  // "1분"은 시안 표시값이 공용 컴포넌트 필러로 추정 — 옵션·기본값 미정(감사 UNKNOWN)
  { id: 'polling-interval', label: '얼마나 자주 갱신할까요?', valueLabel: '1분' },
  { id: 'backfill-range', label: '언제부터의 상담을 가져올까요?', valueLabel: '지금부터' },
  { id: 'run-time', label: '실행 시간', valueLabel: '1분' },
];

export const SCHEDULE_RESULT_TEXT = '매일 자정에 새 상담을 확인하고 문서 초안을 만들어요.';
export const BACKFILL_NOTICE_TEXT = '과거 이력 가져오기는 곧 지원돼요.';

export const ONBOARDING_NEXT_LABEL = '다음단계';
