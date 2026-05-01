import type { SyncTargetItem } from '../types/syncModel';

/**
 * 채널톡 임베딩 모달에서 사용하는 1:N (channel : N spaces) 모델.
 * 기존 mockChannels.ts에서 옮겨온 타입.
 *
 * 백엔드 GET /sync/targets는 channel/space를 flat list로 반환하지만,
 * UI 모델은 "채널 카드 → 그 자식으로 스페이스 N개" 구조라
 * mapChannelTalkSyncTargets로 변환한다.
 */
export interface ChannelTalkDocumentSpace {
  space_id: string;
  display_name: string;
}

export interface ChannelTalkChannel {
  channel_id: string;
  display_name: string;
  document_spaces: ChannelTalkDocumentSpace[];
}

/**
 * 백엔드 flat sync targets → 1:N 모델 변환.
 *
 * 현재 백엔드는 채널 1개 + 도큐먼트 스페이스 1개만 단일 워크스페이스로 저장하므로,
 * channel 목록 각각에 모든 space가 자식으로 묶이는 단순 매핑.
 * 백엔드가 향후 N개 지원 + channel-space 관계 메타데이터 제공 시 이 함수만 수정하면 됨.
 */
export function mapChannelTalkSyncTargets(targets: SyncTargetItem[]): ChannelTalkChannel[] {
  const channels = targets.filter((t) => t.target_type === 'channel');
  const spaces = targets.filter((t) => t.target_type === 'space');

  return channels.map((channel) => ({
    channel_id: channel.target_id,
    display_name: channel.display_name,
    document_spaces: spaces.map((space) => ({
      space_id: space.target_id,
      display_name: space.display_name,
    })),
  }));
}
