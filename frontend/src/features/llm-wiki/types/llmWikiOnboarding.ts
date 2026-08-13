/**
 * LLM Wiki 온보딩(생성 마법사) 타입. 온보딩 제출 API가 백엔드에 없어 화면 계약은 mock이다.
 * [BE]는 server/wiki의 ChannelListItemResponse에 실재하는 필드, [SPEC]은 시안·명세에만 있는 값.
 */

export interface OnboardingStepInfo {
  /** 1부터 시작하는 표시 번호 */
  number: number;
  label: string;
}

/** 목적 선택지. 선택하면 후속 질문이 갈리고, 질문 미확정(커스텀)은 null */
export interface WikiPurposeOption {
  id: string;
  label: string;
  followUpQuestion: string | null;
}

// 아이콘이 정의된 종류만 알려져 있고 나머지는 열어둔다 — 미지 아이콘은 file로 렌더
export type KnownDocKindIcon = 'file' | 'group' | 'graph' | 'search-file';
export type DocKindIcon = KnownDocKindIcon | (string & {});

/** 문서 종류 프리셋(단일 선택). sampleText 뒷부분은 카피 미정 */
export interface WikiDocKindPreset {
  id: string;
  icon: DocKindIcon;
  label: string;
  description: string;
  sampleText: string;
}

/** 문체 카드. 다중 선택 여부가 미확정이라 선택 상태를 목록으로 받는다 */
export interface WikiToneStyleOption {
  id: string;
  label: string;
}

/** [BE] GET /api/v1/wiki/channels 폴더 한 줄 (FolderResponse 대응) */
export interface WikiChannelFolder {
  id: string;
  name: string;
  channelId: string;
}

/** [BE] GET /api/v1/wiki/channels 한 줄 (ChannelListItemResponse의 camelCase 전사) */
export interface WikiChannelListItem {
  id: string;
  name: string;
  workspaceId: number;
  isAdmin: boolean;
  documentCount: number;
  folders: readonly WikiChannelFolder[];
}

/** 채널 표의 행. lastModifiedLabel은 [SPEC] — 백엔드 계약에 수정일 필드가 없다 */
export interface OnboardingChannelRow {
  channel: WikiChannelListItem;
  lastModifiedLabel: string;
}

/** 2단계 수집 일정 필드 하나(닫힌 드롭다운 트리거). 열림 상태는 시안에 없다 */
export interface ScheduleFieldData {
  id: string;
  label: string;
  /** 트리거에 표시되는 현재 값 문자열 */
  valueLabel: string;
}
