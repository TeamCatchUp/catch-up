'use client';

import { useCallback, useMemo, useReducer } from 'react';

import { DEFAULT_PERIOD, type Period } from '../constants/period';
import type { ChannelTalkChannel } from '../utils/mapChannelTalkSyncTargets';

interface ChannelTalkSelectionState {
  // 좌측 토글 — 우측 패널에 ChannelGroup 렌더 여부 (임베딩 선택과 무관)
  visibleChannelIds: Set<string>;
  // 우측 헤더 체크박스 — 이 채널 자체를 임베딩 대상에 포함
  selectedChannelIds: Set<string>;
  selectedSpaceIds: Set<string>;
  channelPeriods: Record<string, Period>;
  // 명시 설정한 space만 보관. 미설정 space는 DEFAULT_PERIOD 사용 (채널과 독립)
  spacePeriods: Record<string, Period>;
}

type ChannelTalkSelectionAction =
  | { type: 'TOGGLE_VISIBLE_CHANNEL'; channelId: string; spaceIds: readonly string[] }
  | { type: 'TOGGLE_CHANNEL'; channelId: string }
  | { type: 'TOGGLE_ALL'; channels: ChannelTalkChannel[] }
  | { type: 'TOGGLE_SPACE'; spaceId: string }
  | { type: 'SET_CHANNEL_PERIOD'; channelId: string; period: Period }
  | { type: 'SET_SPACE_PERIOD'; spaceId: string; period: Period };

function init(channels: ChannelTalkChannel[]): ChannelTalkSelectionState {
  return {
    visibleChannelIds: new Set(),
    selectedChannelIds: new Set(),
    selectedSpaceIds: new Set(),
    channelPeriods: Object.fromEntries(channels.map((channel) => [channel.channel_id, DEFAULT_PERIOD])),
    spacePeriods: {},
  };
}

function toggleSetMember<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function isEverythingSelected(state: ChannelTalkSelectionState, channels: ChannelTalkChannel[]): boolean {
  if (channels.length === 0) return false;
  const allVisible = channels.every((c) => state.visibleChannelIds.has(c.channel_id));
  const allChannels = channels.every((c) => state.selectedChannelIds.has(c.channel_id));
  const allSpaces = channels.every((c) =>
    c.document_spaces.every((s) => state.selectedSpaceIds.has(s.space_id)),
  );
  return allVisible && allChannels && allSpaces;
}

function reducer(state: ChannelTalkSelectionState, action: ChannelTalkSelectionAction): ChannelTalkSelectionState {
  switch (action.type) {
    case 'TOGGLE_VISIBLE_CHANNEL': {
      const { channelId, spaceIds } = action;
      const willTurnOff = state.visibleChannelIds.has(channelId);
      const nextVisible = toggleSetMember(state.visibleChannelIds, channelId);
      if (!willTurnOff) {
        return { ...state, visibleChannelIds: nextVisible };
      }
      // visibility off — 해당 채널과 하위 스페이스의 임베딩 선택도 함께 해제
      const nextChannelIds = new Set(state.selectedChannelIds);
      nextChannelIds.delete(channelId);
      const nextSpaceIds = new Set(state.selectedSpaceIds);
      spaceIds.forEach((id) => nextSpaceIds.delete(id));
      return {
        ...state,
        visibleChannelIds: nextVisible,
        selectedChannelIds: nextChannelIds,
        selectedSpaceIds: nextSpaceIds,
      };
    }
    case 'TOGGLE_CHANNEL':
      return { ...state, selectedChannelIds: toggleSetMember(state.selectedChannelIds, action.channelId) };
    case 'TOGGLE_ALL': {
      const { channels } = action;
      if (isEverythingSelected(state, channels)) {
        return {
          ...state,
          visibleChannelIds: new Set(),
          selectedChannelIds: new Set(),
          selectedSpaceIds: new Set(),
        };
      }
      return {
        ...state,
        visibleChannelIds: new Set(channels.map((c) => c.channel_id)),
        selectedChannelIds: new Set(channels.map((c) => c.channel_id)),
        selectedSpaceIds: new Set(channels.flatMap((c) => c.document_spaces.map((s) => s.space_id))),
      };
    }
    case 'TOGGLE_SPACE':
      return { ...state, selectedSpaceIds: toggleSetMember(state.selectedSpaceIds, action.spaceId) };
    case 'SET_CHANNEL_PERIOD':
      return { ...state, channelPeriods: { ...state.channelPeriods, [action.channelId]: action.period } };
    case 'SET_SPACE_PERIOD':
      return { ...state, spacePeriods: { ...state.spacePeriods, [action.spaceId]: action.period } };
  }
}

// 채널톡 임베딩 모달 selection state.
// visibility(좌측 클릭)와 임베딩 선택(우측 체크박스)을 분리. 채널/스페이스 기간도 독립.
export function useChannelTalkSelection(channels: ChannelTalkChannel[]) {
  const [state, dispatch] = useReducer(reducer, channels, init);

  const channelMap = useMemo(() => {
    const map = new Map<string, ChannelTalkChannel>();
    channels.forEach((channel) => map.set(channel.channel_id, channel));
    return map;
  }, [channels]);

  const visibleChannels = useMemo(
    () => channels.filter((channel) => state.visibleChannelIds.has(channel.channel_id)),
    [channels, state.visibleChannelIds],
  );

  const channelCount = state.selectedChannelIds.size;
  const spaceCount = state.selectedSpaceIds.size;
  const isSubmitDisabled = channelCount === 0 && spaceCount === 0;
  const isAllSelected = useMemo(() => isEverythingSelected(state, channels), [state, channels]);

  const toggleVisibility = useCallback(
    (channelId: string) => {
      const channel = channelMap.get(channelId);
      if (!channel) return;
      const spaceIds = channel.document_spaces.map((space) => space.space_id);
      dispatch({ type: 'TOGGLE_VISIBLE_CHANNEL', channelId, spaceIds });
    },
    [channelMap],
  );

  const toggleChannel = useCallback((channelId: string) => {
    dispatch({ type: 'TOGGLE_CHANNEL', channelId });
  }, []);

  const toggleAll = useCallback(() => {
    dispatch({ type: 'TOGGLE_ALL', channels });
  }, [channels]);

  const toggleSpace = useCallback((spaceId: string) => {
    dispatch({ type: 'TOGGLE_SPACE', spaceId });
  }, []);

  const setChannelPeriod = useCallback((channelId: string, period: Period) => {
    dispatch({ type: 'SET_CHANNEL_PERIOD', channelId, period });
  }, []);

  const setSpacePeriod = useCallback((spaceId: string, period: Period) => {
    dispatch({ type: 'SET_SPACE_PERIOD', spaceId, period });
  }, []);

  return {
    visibleChannelIds: state.visibleChannelIds,
    selectedChannelIds: state.selectedChannelIds,
    selectedSpaceIds: state.selectedSpaceIds,
    channelPeriods: state.channelPeriods,
    spacePeriods: state.spacePeriods,
    visibleChannels,
    channelCount,
    spaceCount,
    isSubmitDisabled,
    isAllSelected,
    toggleVisibility,
    toggleChannel,
    toggleAll,
    toggleSpace,
    setChannelPeriod,
    setSpacePeriod,
  };
}
