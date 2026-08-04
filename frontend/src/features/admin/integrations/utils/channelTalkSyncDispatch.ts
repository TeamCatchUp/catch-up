import { DEFAULT_PERIOD, type Period,PERIOD_SYNC_DAYS } from '../constants/period';
import type { FullSyncTarget } from '../types/syncModel';
import type { ChannelTalkChannel } from './mapChannelTalkSyncTargets';

// 백엔드가 단일 sync_days만 받아 가장 긴 period 채택. '전체' 포함 시 null
export function pickSyncDays(periods: Period[]): number | null {
  if (periods.length === 0) return null;
  let maxDays = 0;
  for (const p of periods) {
    const days = PERIOD_SYNC_DAYS[p];
    if (days === null) return null;
    if (days > maxDays) maxDays = days;
  }
  return maxDays;
}

// 임베딩 1건 = channel scope_id 묶음 (sync targets + 사용된 periods)
export interface ChannelTalkSyncDispatchGroup {
  channel: ChannelTalkChannel;
  targets: FullSyncTarget[];
  periods: Period[];
}

/** POST /sync/full 요청 한 건 — connector는 호출부가 붙인다 */
export interface ChannelTalkSyncRequest {
  scope_id: string;
  targets: FullSyncTarget[];
  sync_days: number | null;
}

/**
 * 선택 상태 → channel별 /sync/full 요청 페이로드.
 * `sync_days`는 **그 채널에서 사용된 기간만으로** 정한다 — 다른 채널의 '전체'
 * 선택이 전염되면 좁게 고른 채널까지 전체 기간으로 동기화된다.
 */
export function buildChannelTalkSyncRequests(
  channels: ChannelTalkChannel[],
  selectedChannelIds: Set<string>,
  selectedSpaceIds: Set<string>,
  channelPeriods: Record<string, Period>,
  spacePeriods: Record<string, Period>,
): ChannelTalkSyncRequest[] {
  return groupChannelTalkSyncDispatch(channels, selectedChannelIds, selectedSpaceIds, channelPeriods, spacePeriods).map(
    ({ channel, targets, periods }) => ({
      scope_id: channel.channel_id,
      targets,
      sync_days: pickSyncDays(periods),
    }),
  );
}

// POST /sync/full은 scope_id 1개라 channel별 1회씩 호출 — 빈 그룹은 제외
export function groupChannelTalkSyncDispatch(
  channels: ChannelTalkChannel[],
  selectedChannelIds: Set<string>,
  selectedSpaceIds: Set<string>,
  channelPeriods: Record<string, Period>,
  spacePeriods: Record<string, Period>,
): ChannelTalkSyncDispatchGroup[] {
  return channels
    .map<ChannelTalkSyncDispatchGroup>((channel) => {
      const targets: FullSyncTarget[] = [];
      const periods: Period[] = [];

      if (selectedChannelIds.has(channel.channel_id)) {
        targets.push({ target_type: 'channel', target_id: channel.channel_id });
        periods.push(channelPeriods[channel.channel_id] ?? DEFAULT_PERIOD);
      }

      for (const space of channel.document_spaces) {
        if (!selectedSpaceIds.has(space.space_id)) continue;
        targets.push({ target_type: 'space', target_id: space.space_id });
        // space 기간은 채널과 독립. 미설정 시 DEFAULT_PERIOD ('전체')
        periods.push(spacePeriods[space.space_id] ?? DEFAULT_PERIOD);
      }

      return { channel, targets, periods };
    })
    .filter((g) => g.targets.length > 0);
}
