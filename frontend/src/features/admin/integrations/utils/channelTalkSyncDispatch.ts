import { DEFAULT_PERIOD, type Period } from '../constants/period';
import type { FullSyncTarget } from '../types/syncModel';
import type { ChannelTalkChannel } from './mapChannelTalkSyncTargets';

// Period 라벨 → 백엔드 sync_days. '전체' = null → 백엔드 기본값(1095) 사용
const PERIOD_TO_DAYS: Record<Period, number | null> = {
  '1개월': 30,
  '3개월': 90,
  '6개월': 180,
  '1년': 365,
  '3년': 1095,
  전체: null,
};

// 백엔드가 단일 sync_days만 받아 가장 긴 period 채택. '전체' 포함 시 null
export function pickSyncDays(periods: Period[]): number | null {
  if (periods.length === 0) return null;
  let maxDays = 0;
  for (const p of periods) {
    const days = PERIOD_TO_DAYS[p];
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
        // 명시 설정 없으면 부모 channel period 상속
        const explicit = spacePeriods[space.space_id];
        if (explicit) periods.push(explicit);
      }

      return { channel, targets, periods };
    })
    .filter((g) => g.targets.length > 0);
}
