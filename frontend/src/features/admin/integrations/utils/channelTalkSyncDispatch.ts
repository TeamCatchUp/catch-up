import { DEFAULT_PERIOD, type Period } from '../components/member/modals/channelTalk/PeriodSelect';
import type { FullSyncTarget } from '../types/syncModel';
import type { ChannelTalkChannel } from './mapChannelTalkSyncTargets';

/** Period(한국어 라벨) → 백엔드 sync_days 일수. '전체'는 null로 백엔드 기본값(1095) 사용. */
const PERIOD_TO_DAYS: Record<Period, number | null> = {
  '1개월': 30,
  '3개월': 90,
  '6개월': 180,
  '1년': 365,
  '3년': 1095,
  전체: null,
};

/**
 * 선택된 target들의 period 중 가장 긴 일수를 sync_days로 사용.
 * '전체'(null)가 하나라도 포함되면 즉시 null 반환 → 백엔드 기본값(1095) 사용.
 *
 * 백엔드는 단일 sync_days만 받으므로 보수적으로 가장 넓은 기간 채택.
 * channel별 다른 period를 분리해서 보내려면 백엔드 schema 변경이 필요하다.
 */
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

/** 임베딩 요청 1건 — channel scope_id에 묶인 sync targets + 그 channel에서 사용된 period들 */
export interface ChannelTalkSyncDispatchGroup {
  channel: ChannelTalkChannel;
  targets: FullSyncTarget[];
  periods: Period[];
}

/**
 * 사용자가 선택한 채널/스페이스를 channel scope별로 그룹화.
 *
 * 백엔드 `POST /sync/full`은 scope_id 1개만 받기 때문에 channel당 1번씩 mutation을
 * 호출해야 한다. 이 함수는 그 호출 단위를 미리 묶어 반환한다. targets가 비어있는
 * channel은 결과에서 제외 (호출 불필요).
 */
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
        // space는 명시 설정이 없으면 부모 channel period 상속.
        const explicit = spacePeriods[space.space_id];
        if (explicit) periods.push(explicit);
      }

      return { channel, targets, periods };
    })
    .filter((g) => g.targets.length > 0);
}

/** 채널톡 sync 결과 집계 — 토스트 노출에 사용 */
export interface ChannelTalkSyncResultSummary {
  acceptedCount: number;
  conflictCount: number;
  noEventsCount: number;
  failedCount: number;
  errorCount: number;
  /** 첫 번째 발견된 실패 메시지 (사용자 대면 토스트용) */
  lastFailMessage: string | null;
  /** mutation 응답에서 추적 시작할 job_id 목록 (accepted + conflict 모두) */
  jobIdsToTrack: string[];
}
