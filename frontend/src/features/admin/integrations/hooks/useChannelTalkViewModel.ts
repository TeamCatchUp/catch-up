'use client';

import { useState } from 'react';

import { CHANNEL_TALK_MOCK_STATE } from '../constants/channelTalkMock';
import type { ChannelTalkConnectionState } from '../types/channelTalkModel';

/**
 * 채널톡 연동 뷰모델 — UI에 필요한 채널톡 상태를 단일 진입점으로 제공.
 *
 * **현재**: `constants/channelTalkMock.ts`의 정적 mock 데이터를 그대로 반환.
 * **향후 (channel-talk-api PR)**: 본 hook 내부의 mock import 제거 + `useQuery` 1줄로 교체.
 *   컴포넌트 코드는 변경되지 않는다 (props는 ChannelTalkConnectionState model에만 의존).
 */
export function useChannelTalkViewModel(): ChannelTalkConnectionState {
  const [state] = useState(CHANNEL_TALK_MOCK_STATE);
  return state;
}
