// 갤러리 항목 메타데이터. Sidebar 와 [slug] 페이지가 공유하는 source of truth.

export type EntrySlug =
  | 'text-content'
  | 'block-content'
  | 'button-content'
  | 'form-content'
  | 'file-content'
  | 'message-item'
  | 'date-indicator'
  | 'consultation-info'
  | 'customer-info'
  | 'collapsible'
  | 'panel-skeleton'
  | 'panel-empty'
  | 'panel-error'
  | 'panel-coming-soon'
  | 'panel-content'
  | 'panel';

export type EntryGroup =
  | 'contents'
  | 'messages'
  | 'info'
  | 'primitives'
  | 'panel-states'
  | 'assembled';

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
  contents: 'Contents',
  messages: 'Messages',
  info: 'Info',
  primitives: 'Primitives',
  'panel-states': 'Panel States',
  assembled: 'Assembled',
};

export const GALLERY_ENTRIES: readonly GalleryEntry[] = [
  // contents
  {
    slug: 'text-content',
    title: 'TextContent',
    group: 'contents',
    description: 'payload.text 를 줄바꿈 보존 평문으로 렌더.',
  },
  {
    slug: 'block-content',
    title: 'BlockContent',
    group: 'contents',
    description: 'blocks[] 를 block_type 별로 분기 — text→마크다운, code→코드블럭, bullets→리스트.',
  },
  {
    slug: 'button-content',
    title: 'ButtonContent',
    group: 'contents',
    description: 'buttons[] 를 공통 Button 으로 렌더 — url 있는 버튼만 새 탭 링크.',
  },
  {
    slug: 'form-content',
    title: 'FormContent',
    group: 'contents',
    description: 'form.inputs[] 라벨/값 행과 제출 시각. 모든 행 인라인 노출.',
  },
  {
    slug: 'file-content',
    title: 'FileContent',
    group: 'contents',
    description: 'files[] 각 요소를 FileRow 로 — 안전 다운로드 링크.',
  },
  // messages
  {
    slug: 'message-item',
    title: 'MessageItem',
    group: 'messages',
    description: 'visibility + author.type 별 변형. customer=blue stripe, manager internal=orange stripe+bg.',
  },
  {
    slug: 'date-indicator',
    title: 'DateIndicator',
    group: 'messages',
    description: '채팅 타임라인의 날짜 구분선.',
  },
  // info
  {
    slug: 'consultation-info',
    title: 'ConsultationInfo',
    group: 'info',
    description: '담당자/상담 태그/상담 설명. 138px 라벨 컬럼 고정.',
  },
  {
    slug: 'customer-info',
    title: 'CustomerInfo',
    group: 'info',
    description: '고객 이름/이메일/전화번호/유선번호. 접기/펴기.',
  },
  // primitives
  {
    slug: 'collapsible',
    title: 'Collapsible',
    group: 'primitives',
    description: 'controlled 접기/펴기 primitive.',
  },
  // panel-states
  {
    slug: 'panel-skeleton',
    title: 'OriginalPanelSkeleton',
    group: 'panel-states',
    description: '로딩 중 패널 골격.',
  },
  {
    slug: 'panel-empty',
    title: 'OriginalPanelEmpty',
    group: 'panel-states',
    description: '선택된 문서가 없을 때.',
  },
  {
    slug: 'panel-error',
    title: 'OriginalPanelError',
    group: 'panel-states',
    description: 'API 오류 (400/404/422 분기).',
  },
  {
    slug: 'panel-coming-soon',
    title: 'OriginalPanelComingSoon',
    group: 'panel-states',
    description: 'user_chat 아닌 소스 — 툴명 보간.',
  },
  // assembled
  {
    slug: 'panel-content',
    title: 'OriginalPanelContent',
    group: 'assembled',
    description: '상담정보 → 고객정보 → 메시지 영역 전체 조립.',
  },
  {
    slug: 'panel',
    title: 'OriginalPanel',
    group: 'assembled',
    description: 'connector/entityType/documentId 로 상태 분기하는 컨테이너.',
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
