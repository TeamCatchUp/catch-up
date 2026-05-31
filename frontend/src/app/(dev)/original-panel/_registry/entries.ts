// 갤러리 항목 메타데이터. Sidebar 와 [slug] 페이지가 공유하는 source of truth.
// title 은 디자이너 친화 한국어. slug 는 URL (kebab-case, 변경 시 북마크 깨짐).

export type EntrySlug =
  | 'text-content'
  | 'block-content'
  | 'button-content'
  | 'form-content'
  | 'file-content'
  | 'message-item'
  | 'date-indicator'
  | 'slack-thread-header'
  | 'slack-message-item'
  | 'slack-rich-message'
  | 'consultation-info'
  | 'customer-info'
  | 'collapsible'
  | 'panel-skeleton'
  | 'panel-empty'
  | 'panel-error'
  | 'panel-coming-soon'
  | 'panel-content'
  | 'slack-panel-preview'
  | 'panel';

export type EntryGroup = 'contents' | 'messages' | 'info' | 'primitives' | 'panel-states' | 'assembled';

export interface GalleryEntry {
  slug: EntrySlug;
  title: string;
  group: EntryGroup;
  description?: string;
}

export const GROUP_ORDER: readonly EntryGroup[] = [
  'contents',
  'messages',
  'info',
  'primitives',
  'panel-states',
  'assembled',
];

export const GROUP_LABELS: Record<EntryGroup, string> = {
  contents: '콘텐츠',
  messages: '메시지',
  info: '정보',
  primitives: '공통 요소',
  'panel-states': '패널 상태',
  assembled: '조립',
};

export const GALLERY_ENTRIES: readonly GalleryEntry[] = [
  // 콘텐츠
  {
    slug: 'text-content',
    title: '텍스트',
    group: 'contents',
    description: '평문 텍스트 — 줄바꿈 보존.',
  },
  {
    slug: 'block-content',
    title: '블록 (마크다운·코드·불릿)',
    group: 'contents',
    description: '마크다운 텍스트 / 코드 / 불릿 리스트로 분기해 렌더.',
  },
  {
    slug: 'button-content',
    title: '버튼',
    group: 'contents',
    description: 'url 있는 버튼만 새 탭 링크. 공통 Button 컴포넌트 사용.',
  },
  {
    slug: 'form-content',
    title: '폼',
    group: 'contents',
    description: '입력 항목 라벨/값 + 제출 시각. 모든 행 인라인 노출.',
  },
  {
    slug: 'file-content',
    title: '파일',
    group: 'contents',
    description: '파일명 + 크기·타입 + 안전 다운로드 링크.',
  },
  // 메시지
  {
    slug: 'message-item',
    title: '메시지 말풍선',
    group: 'messages',
    description: '문의자(파란 stripe+bg) / 내부 대화(주황 stripe+bg) / 일반 상담원 변형.',
  },
  {
    slug: 'date-indicator',
    title: '날짜 구분선',
    group: 'messages',
    description: '채팅 타임라인 날짜별 구분 표시.',
  },
  {
    slug: 'slack-thread-header',
    title: 'Slack 스레드 헤더',
    group: 'messages',
    description: 'Slack 채널명과 참여자 목록 헤더.',
  },
  {
    slug: 'slack-message-item',
    title: 'Slack 일반 메시지',
    group: 'messages',
    description: 'Slack 유저 메시지 row.',
  },
  {
    slug: 'slack-rich-message',
    title: 'Slack Rich 메시지',
    group: 'messages',
    description: 'Slack bot, rich text, 파일, 링크, 이미지 케이스.',
  },
  // 정보
  {
    slug: 'consultation-info',
    title: '상담 정보',
    group: 'info',
    description: '담당자 / 상담 태그 / 상담 설명. 라벨 컬럼 138px 고정.',
  },
  {
    slug: 'customer-info',
    title: '고객 정보',
    group: 'info',
    description: '이름 / 이메일 / 전화번호 / 유선번호. 접기·펴기.',
  },
  // 공통 요소
  {
    slug: 'collapsible',
    title: '접기·펴기',
    group: 'primitives',
    description: 'controlled expand/collapse primitive. 고객정보·폼이 사용.',
  },
  // 패널 상태
  {
    slug: 'panel-skeleton',
    title: '로딩 스켈레톤',
    group: 'panel-states',
    description: '원문 데이터 로딩 중 표시.',
  },
  {
    slug: 'panel-empty',
    title: '빈 상태',
    group: 'panel-states',
    description: '선택된 문서가 없을 때.',
  },
  {
    slug: 'panel-error',
    title: '에러 상태',
    group: 'panel-states',
    description: 'API 오류 (400 지원 안 함 / 404 연동 없음 / 422 제공처 오류).',
  },
  {
    slug: 'panel-coming-soon',
    title: '준비 중',
    group: 'panel-states',
    description: 'ChannelTalk user_chat 외 다른 소스 선택 시 — 툴명 보간.',
  },
  // 조립
  {
    slug: 'panel-content',
    title: '본문 (전체 조립)',
    group: 'assembled',
    description: '상담 정보 → 고객 정보 → 메시지 영역의 전체 조립 결과.',
  },
  {
    slug: 'slack-panel-preview',
    title: 'Slack 원문 패널',
    group: 'assembled',
    description: 'Slack thread 원문 패널 dev preview.',
  },
  {
    slug: 'panel',
    title: '컨테이너 (상태 분기)',
    group: 'assembled',
    description: 'connector/entityType/documentId 입력 → 위 상태들 중 하나로 분기.',
  },
];

// group 별 entries 사전 분류 — sidebar 렌더에 사용.
export const GROUPED_ENTRIES: Record<EntryGroup, GalleryEntry[]> = (() => {
  const result: Record<EntryGroup, GalleryEntry[]> = {
    contents: [],
    messages: [],
    info: [],
    primitives: [],
    'panel-states': [],
    assembled: [],
  };
  for (const entry of GALLERY_ENTRIES) {
    result[entry.group].push(entry);
  }
  return result;
})();
