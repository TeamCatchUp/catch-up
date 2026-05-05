'use client';

import { useCallback, useMemo, useReducer } from 'react';
import { toast } from 'sonner';

import { DEFAULT_PERIOD, type Period } from '../constants/period';
import type { ChannelTalkChannel } from '../utils/mapChannelTalkSyncTargets';

interface ChannelTalkSelectionState {
  selectedChannelIds: Set<string>;
  selectedSpaceIds: Set<string>;
  channelPeriods: Record<string, Period>;
  /** 사용자가 명시 설정한 space만 보관. 미설정 space는 채널 기간을 inheritance로 따라간다. */
  spacePeriods: Record<string, Period>;
}

type ChannelTalkSelectionAction =
  | { type: 'TOGGLE_CHANNEL'; channel: ChannelTalkChannel }
  | { type: 'TOGGLE_ALL_CHANNELS'; channels: ChannelTalkChannel[] }
  | { type: 'TOGGLE_SPACE'; spaceId: string }
  | { type: 'TOGGLE_CHANNEL_SPACES'; channel: ChannelTalkChannel }
  | { type: 'SET_CHANNEL_PERIOD'; channelId: string; period: Period }
  | { type: 'SET_SPACE_PERIOD'; spaceId: string; period: Period };

function init(channels: ChannelTalkChannel[]): ChannelTalkSelectionState {
  return {
    selectedChannelIds: new Set(channels.map((channel) => channel.channel_id)),
    selectedSpaceIds: new Set(channels.flatMap((channel) => channel.document_spaces.map((space) => space.space_id))),
    channelPeriods: Object.fromEntries(channels.map((channel) => [channel.channel_id, DEFAULT_PERIOD])),
    spacePeriods: {},
  };
}

function reducer(state: ChannelTalkSelectionState, action: ChannelTalkSelectionAction): ChannelTalkSelectionState {
  switch (action.type) {
    case 'TOGGLE_CHANNEL': {
      const { channel } = action;
      const willSelect = !state.selectedChannelIds.has(channel.channel_id);
      const nextChannelIds = new Set(state.selectedChannelIds);
      const nextSpaceIds = new Set(state.selectedSpaceIds);

      if (willSelect) {
        nextChannelIds.add(channel.channel_id);
        channel.document_spaces.forEach((space) => nextSpaceIds.add(space.space_id));
      } else {
        nextChannelIds.delete(channel.channel_id);
        channel.document_spaces.forEach((space) => nextSpaceIds.delete(space.space_id));
      }

      return { ...state, selectedChannelIds: nextChannelIds, selectedSpaceIds: nextSpaceIds };
    }
    case 'TOGGLE_ALL_CHANNELS': {
      const { channels } = action;
      const isAllSelected =
        channels.length > 0 && channels.every((channel) => state.selectedChannelIds.has(channel.channel_id));
      if (isAllSelected) {
        return { ...state, selectedChannelIds: new Set(), selectedSpaceIds: new Set() };
      }
      return {
        ...state,
        selectedChannelIds: new Set(channels.map((channel) => channel.channel_id)),
        selectedSpaceIds: new Set(
          channels.flatMap((channel) => channel.document_spaces.map((space) => space.space_id)),
        ),
      };
    }
    case 'TOGGLE_SPACE': {
      const next = new Set(state.selectedSpaceIds);
      if (next.has(action.spaceId)) next.delete(action.spaceId);
      else next.add(action.spaceId);
      return { ...state, selectedSpaceIds: next };
    }
    case 'TOGGLE_CHANNEL_SPACES': {
      const { channel } = action;
      const allSelected = channel.document_spaces.every((space) => state.selectedSpaceIds.has(space.space_id));
      const next = new Set(state.selectedSpaceIds);
      channel.document_spaces.forEach((space) => {
        if (allSelected) next.delete(space.space_id);
        else next.add(space.space_id);
      });
      return { ...state, selectedSpaceIds: next };
    }
    case 'SET_CHANNEL_PERIOD':
      return { ...state, channelPeriods: { ...state.channelPeriods, [action.channelId]: action.period } };
    case 'SET_SPACE_PERIOD':
      return { ...state, spacePeriods: { ...state.spacePeriods, [action.spaceId]: action.period } };
  }
}

/**
 * 채널톡 임베딩 모달의 selection 로직을 useReducer로 응집한 훅.
 *
 * - 4개 state(채널/스페이스 선택, 채널/스페이스 기간)를 단일 state object + 6개 action으로 관리
 * - reducer는 pure (외부 변수 수정 없음, 부수 효과는 반환된 dispatch 호출 후 handler 본문에서 처리)
 * - 초기 상태: 모든 채널/스페이스 선택 + 모든 채널 기간 DEFAULT_PERIOD + spacePeriods는 빈 객체(inheritance)
 * - 좌측 채널 토글 시 해당 채널의 도큐먼트 스페이스도 함께 add/delete (양방향 동기화)
 */
export function useChannelTalkSelection(channels: ChannelTalkChannel[]) {
  const [state, dispatch] = useReducer(reducer, channels, init);

  const channelMap = useMemo(() => {
    const map = new Map<string, ChannelTalkChannel>();
    channels.forEach((channel) => map.set(channel.channel_id, channel));
    return map;
  }, [channels]);

  const visibleChannels = useMemo(
    () => channels.filter((channel) => state.selectedChannelIds.has(channel.channel_id)),
    [channels, state.selectedChannelIds],
  );

  const channelCount = state.selectedChannelIds.size;
  const spaceCount = state.selectedSpaceIds.size;
  const isSubmitDisabled = channelCount === 0 || spaceCount === 0;

  const toggleChannel = useCallback(
    (channelId: string) => {
      const channel = channelMap.get(channelId);
      if (!channel) return;

      // 토스트는 dispatch 전에 latest state로 willSelect를 결정해 분기.
      const willSelect = !state.selectedChannelIds.has(channelId);
      dispatch({ type: 'TOGGLE_CHANNEL', channel });

      if (!willSelect && channel.document_spaces.length > 0) {
        toast(`${channel.display_name} 선택 해제되었습니다`, {
          description: `${channel.document_spaces.length}개의 도큐먼트 스페이스가 모두 선택 해제되었습니다`,
        });
      }
    },
    [channelMap, state.selectedChannelIds],
  );

  const toggleAllChannels = useCallback(() => {
    dispatch({ type: 'TOGGLE_ALL_CHANNELS', channels });
  }, [channels]);

  const toggleSpace = useCallback((spaceId: string) => {
    dispatch({ type: 'TOGGLE_SPACE', spaceId });
  }, []);

  const toggleChannelSpaces = useCallback(
    (channelId: string) => {
      const channel = channelMap.get(channelId);
      if (!channel) return;
      dispatch({ type: 'TOGGLE_CHANNEL_SPACES', channel });
    },
    [channelMap],
  );

  const setChannelPeriod = useCallback((channelId: string, period: Period) => {
    dispatch({ type: 'SET_CHANNEL_PERIOD', channelId, period });
  }, []);

  const setSpacePeriod = useCallback((spaceId: string, period: Period) => {
    dispatch({ type: 'SET_SPACE_PERIOD', spaceId, period });
  }, []);

  return {
    selectedChannelIds: state.selectedChannelIds,
    selectedSpaceIds: state.selectedSpaceIds,
    channelPeriods: state.channelPeriods,
    spacePeriods: state.spacePeriods,
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
