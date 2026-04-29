'use client';

import { useMemo, useState } from 'react';

import type { ChannelTalkChannel } from '../components/member/modals/channelTalk/mockChannels';
import { DEFAULT_PERIOD, type Period } from '../components/member/modals/channelTalk/PeriodSelect';

/**
 * 채널톡 임베딩 모달의 selection 로직(채널/스페이스 체크 + 기간 선택)을 응집한 훅.
 *
 * 초기 상태: 모든 채널/스페이스 선택 + 모든 기간 DEFAULT_PERIOD.
 * 좌측 채널 토글 시 해당 채널의 도큐먼트 스페이스도 함께 add/delete (양방향 동기화).
 */
export function useChannelTalkSelection(channels: ChannelTalkChannel[]) {
  const [selectedChannelIds, setSelectedChannelIds] = useState<Set<string>>(
    () => new Set(channels.map((channel) => channel.channel_id)),
  );
  const [selectedSpaceIds, setSelectedSpaceIds] = useState<Set<string>>(
    () => new Set(channels.flatMap((channel) => channel.document_spaces.map((space) => space.space_id))),
  );
  const [channelPeriods, setChannelPeriods] = useState<Record<string, Period>>(() =>
    Object.fromEntries(channels.map((channel) => [channel.channel_id, DEFAULT_PERIOD])),
  );
  const [spacePeriods, setSpacePeriods] = useState<Record<string, Period>>(() =>
    Object.fromEntries(
      channels.flatMap((channel) => channel.document_spaces.map((space) => [space.space_id, DEFAULT_PERIOD])),
    ),
  );

  const channelMap = useMemo(() => {
    const map = new Map<string, ChannelTalkChannel>();
    channels.forEach((channel) => map.set(channel.channel_id, channel));
    return map;
  }, [channels]);

  const visibleChannels = useMemo(
    () => channels.filter((channel) => selectedChannelIds.has(channel.channel_id)),
    [channels, selectedChannelIds],
  );

  const channelCount = selectedChannelIds.size;
  const spaceCount = selectedSpaceIds.size;
  const isSubmitDisabled = channelCount === 0 || spaceCount === 0;

  const toggleChannel = (channelId: string) => {
    const channel = channelMap.get(channelId);
    if (!channel) return;
    const willSelect = !selectedChannelIds.has(channelId);

    setSelectedChannelIds((prev) => {
      const next = new Set(prev);
      if (willSelect) next.add(channelId);
      else next.delete(channelId);
      return next;
    });
    setSelectedSpaceIds((prev) => {
      const next = new Set(prev);
      channel.document_spaces.forEach((space) => {
        if (willSelect) next.add(space.space_id);
        else next.delete(space.space_id);
      });
      return next;
    });
  };

  const toggleAllChannels = () => {
    const isAllSelected =
      channels.length > 0 && channels.every((channel) => selectedChannelIds.has(channel.channel_id));
    if (isAllSelected) {
      setSelectedChannelIds(new Set());
      setSelectedSpaceIds(new Set());
    } else {
      setSelectedChannelIds(new Set(channels.map((channel) => channel.channel_id)));
      setSelectedSpaceIds(
        new Set(channels.flatMap((channel) => channel.document_spaces.map((space) => space.space_id))),
      );
    }
  };

  const toggleSpace = (spaceId: string) => {
    setSelectedSpaceIds((prev) => {
      const next = new Set(prev);
      if (next.has(spaceId)) next.delete(spaceId);
      else next.add(spaceId);
      return next;
    });
  };

  /** 한 채널 안의 모든 도큐먼트 스페이스를 일괄 토글. 우측 채널 헤더 체크박스가 호출. */
  const toggleChannelSpaces = (channelId: string) => {
    const channel = channelMap.get(channelId);
    if (!channel) return;
    const allSelected = channel.document_spaces.every((space) => selectedSpaceIds.has(space.space_id));
    setSelectedSpaceIds((prev) => {
      const next = new Set(prev);
      channel.document_spaces.forEach((space) => {
        if (allSelected) next.delete(space.space_id);
        else next.add(space.space_id);
      });
      return next;
    });
  };

  const setChannelPeriod = (channelId: string, period: Period) => {
    setChannelPeriods((prev) => ({ ...prev, [channelId]: period }));
  };

  const setSpacePeriod = (spaceId: string, period: Period) => {
    setSpacePeriods((prev) => ({ ...prev, [spaceId]: period }));
  };

  return {
    selectedChannelIds,
    selectedSpaceIds,
    channelPeriods,
    spacePeriods,
    visibleChannels,
    channelCount,
    spaceCount,
    isSubmitDisabled,
    toggleChannel,
    toggleAllChannels,
    toggleSpace,
    toggleChannelSpaces,
    setChannelPeriod,
    setSpacePeriod,
  };
}
