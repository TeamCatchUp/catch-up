import type { SyncTargetItem } from '../types/syncModel';

// 임베딩 모달 1:N (channel : N spaces) 모델
export interface ChannelTalkDocumentSpace {
  space_id: string;
  display_name: string;
}

export interface ChannelTalkChannel {
  channel_id: string;
  display_name: string;
  document_spaces: ChannelTalkDocumentSpace[];
}

// 백엔드 flat sync targets → 1:N 변환. 호출 단위가 channel 1개씩이라 첫 channel에만 space 귀속
export function mapChannelTalkSyncTargets(targets: SyncTargetItem[]): ChannelTalkChannel[] {
  const channels = targets.filter((t) => t.target_type === 'channel');
  const spaces = targets.filter((t) => t.target_type === 'space');

  if (channels.length === 0) return [];

  return channels.map((channel, index) => ({
    channel_id: channel.target_id,
    display_name: channel.display_name,
    // 응답에 다중 channel이 와도 space 소속 알 수 없어 첫 channel에 귀속
    document_spaces:
      index === 0
        ? spaces.map((space) => ({
            space_id: space.target_id,
            display_name: space.display_name,
          }))
        : [],
  }));
}
