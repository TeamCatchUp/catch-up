/**
 * LLM Wiki 온보딩(생성 마법사) 타입. 온보딩 제출 API가 백엔드에 없어 화면 계약은 mock이다.
 * 채널 [BE] 타입은 llmWikiModel이 원천이고, [SPEC]은 시안·명세에만 있는 값이다.
 */

import type { WikiChannelListItem } from './llmWikiModel';

export interface OnboardingStepInfo {
  /** 1부터 시작하는 표시 번호 */
  number: number;
  label: string;
}

/** 목적 선택지. 정보 카테고리를 고르면 그 아래로 갈린다 */
export interface WikiPurposeOption {
  id: string;
  label: string;
}

/**
 * [SPEC] 1단계 정보 카테고리 칩.
 * 시안은 "고객 문의 (VOC)"를 고른 상태만 그려 나머지 카테고리의 목적 목록은 미정이다 —
 * 빈 배열이면 목적 구역을 렌더하지 않는다.
 */
export interface WikiInfoCategory {
  id: string;
  label: string;
  purposeOptions: readonly WikiPurposeOption[];
}

// 문서 종류 아이콘. 시안 6종만 알려져 있고 나머지는 열어둔다 — 미지 아이콘은 file로 렌더
export type KnownDocKindIcon = 'request' | 'error' | 'help' | 'client' | 'history' | 'book';
export type DocKindIcon = KnownDocKindIcon | (string & {});

/** 문서 종류 프리셋(단일 선택). 우측 템플릿 예시는 선택 연동 여부가 미정이라 여기 두지 않는다 */
export interface WikiDocKindPreset {
  id: string;
  icon: DocKindIcon;
  label: string;
  description: string;
}

/** 문체 카드(단일 선택). 예시 문장은 8/14 시안에서 실카피로 확보됐다 */
export interface WikiToneStyleOption {
  id: string;
  label: string;
  description: string;
  sampleText: string;
}

/** 채널 표의 행. 채널 실물은 llmWikiModel의 [BE] 타입을 그대로 소비한다 */
export interface OnboardingChannelRow {
  channel: WikiChannelListItem;
  /** [SPEC] 시안의 "최근 수정일" 열 — 백엔드 계약에 대응 필드가 없다 */
  lastModifiedLabel: string;
}

/**
 * 채널 목록 조회 상태. 시안에 없고 사용자 승인으로 들어간 상태다(감사 §3 참조).
 * 빈 목록은 별도 값이 아니라 ready + 행 0으로 판정한다 — 로딩과 구분되는 지점이 그것뿐이다.
 */
export type OnboardingChannelListStatus = 'loading' | 'ready' | 'error';

/** 2단계 수집 일정 필드 하나(닫힌 드롭다운 트리거). 열림 상태는 시안에 없다 */
export interface ScheduleFieldData {
  id: string;
  label: string;
  /** 트리거에 표시되는 현재 값 문자열 */
  valueLabel: string;
}

/** [SPEC] 완료 화면 요약 행. 문서 종류·채널처럼 값이 여러 개인 행이 있어 배열이다 */
export interface OnboardingSummaryRow {
  label: string;
  values: readonly string[];
}

/** [SPEC] 완료 화면 요약 구역(위키 목적 / 수집 설정) */
export interface OnboardingSummarySection {
  title: string;
  rows: readonly OnboardingSummaryRow[];
}
