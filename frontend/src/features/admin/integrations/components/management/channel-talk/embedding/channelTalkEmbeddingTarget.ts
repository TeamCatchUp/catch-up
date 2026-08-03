import type { Period } from '../../../../constants/period';

/**
 * 임베딩 대상 선택기가 다루는 모델.
 * Figma `17414:97988` — 좌 채널 목록 / 우 채널 그룹 + 도큐먼트 스페이스.
 *
 * 기간은 기존 `constants/period.ts`의 {@link Period}다 — 백엔드 `sync_days`
 * 매핑(`channelTalkSyncDispatch`)까지 이미 있다.
 *
 * 백엔드 응답 타입(`mapChannelTalkSyncTargets`의 `ChannelTalkChannel`)과 분리해
 * 둔다. 선택기는 화면 상태만 알면 되고, 어느 필드로 채울지는 계획 ④에서 정한다.
 */
export interface ChannelTalkDocumentTarget {
  id: string;
  name: string;
  /** 이 도큐먼트 스페이스에 적용된 데이터 기간 */
  dataRange: Period;
}

export interface ChannelTalkChannelTarget {
  id: string;
  name: string;
  /** 채널 대화에 적용된 데이터 기간 */
  dataRange: Period;
  documentSpaces: readonly ChannelTalkDocumentTarget[];
}
