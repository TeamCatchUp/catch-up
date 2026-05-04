import { toast } from 'sonner';

import type {
  ChannelTalkChannel,
  ChannelTalkConnectionStatus,
  ChannelTalkDocumentSpace,
  ChannelTalkFieldState,
  ChannelTalkTestButtonStatus,
} from '../types/channelTalkModel';

/** secret 입력 필드 이름 (채널 + 도큐먼트 스페이스 공용 union) */
export type ChannelTalkSecretFieldName = 'accessKey' | 'accessSecret' | 'webhookToken';

/**
 * connectionStatus → 각 textfield의 시각 변형 매핑.
 * `editing` 상태에서는 사용자가 첫 secret(`accessKey`)을 수정 중이라는 디자인 시안 의도에 따라
 * 그 필드만 focus border, 나머지는 idle border를 사용한다.
 */
export function fieldStateFor(
  status: ChannelTalkConnectionStatus,
  fieldName: ChannelTalkSecretFieldName,
): ChannelTalkFieldState {
  if (status === 'error') return 'error';
  if (status === 'editing' && fieldName === 'accessKey') return 'focus';
  return 'idle';
}

/** connectionStatus → 헤더 "테스트 완료" 라벨 표시용 상태 매핑 */
export function testButtonStatusFor(status: ChannelTalkConnectionStatus): ChannelTalkTestButtonStatus {
  if (status === 'tested') return 'success';
  if (status === 'editing') return 'active';
  return 'idle';
}

/** 채널의 모든 secret(Access Key + Access Secret + Webhook Token)이 채워졌는지 — 화이트스페이스 제외 */
export function isChannelSecretsFilled(channel: ChannelTalkChannel): boolean {
  return Boolean(channel.accessKey.trim() && channel.accessSecret.trim() && channel.webhookToken.trim());
}

/** 도큐먼트 스페이스의 모든 secret(Access Key + Access Secret)이 채워졌는지 — Webhook Token 없음 */
export function isDocumentSpaceSecretsFilled(ds: ChannelTalkDocumentSpace): boolean {
  return Boolean(ds.accessKey.trim() && ds.accessSecret.trim());
}

/**
 * tested(lock) 상태에서 input/dropdown 영역 클릭 시 토스트로 안내.
 * eye 토글 버튼(`data-mask-toggle="true"`) 클릭은 마스킹 해제용이라 예외 처리.
 */
export function handleLockedFieldInteract(e: React.PointerEvent<HTMLDivElement>, isTested: boolean): void {
  if (!isTested) return;
  if ((e.target as HTMLElement).closest('[data-mask-toggle="true"]')) return;
  toast('수정하려면 수정하기 버튼을 눌러주세요.');
}
