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
 * `GET /sync/targets`는 단일 scope_id (= channel_id) 단위로 호출되므로, 응답에는
 * 항상 1개 channel + 그 자식 N개 space가 포함된다. 따라서 변환 결과도 channel 1개에
 * 모든 space를 자식으로 묶는 게 정확하다.
 *
 * 만약 응답에 channel 2개 이상이 들어오면 (예상치 못한 백엔드 변경), 가장 먼저 등장한
 * channel에만 space를 묶고 나머지는 빈 채널로 만들어 잘못된 카르테시안 곱을 피한다.
 *
 * 호출처는 `useQueries`로 channel별 응답을 받아서 각각 이 함수를 통과시킨 후
 * `flatMap`으로 합치므로, 호출 단위로는 channel 1개씩만 들어오는 게 정상.
 */
export function mapChannelTalkSyncTargets(targets: SyncTargetItem[]): ChannelTalkChannel[] {
  const channels = targets.filter((t) => t.target_type === 'channel');
  const spaces = targets.filter((t) => t.target_type === 'space');

  if (channels.length === 0) return [];

  return channels.map((channel, index) => ({
    channel_id: channel.target_id,
    display_name: channel.display_name,
    // 첫 channel에만 모든 space를 묶음. 같은 응답에 다중 channel이 들어와도 space가 어느 channel에
    // 속하는지 알 수 없으므로 보수적으로 한쪽에만 귀속시킨다.
    document_spaces:
      index === 0
        ? spaces.map((space) => ({
            space_id: space.target_id,
            display_name: space.display_name,
          }))
        : [],
  }));
}
