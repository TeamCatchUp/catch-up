'use client';

import { cn } from '@/shared/utils/cn';

import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';
import ChannelTalkNameIcon from './ChannelTalkNameIcon';

interface ChannelTalkChannelListPanelProps {
  channels: readonly ChannelTalkChannelTarget[];
  activeChannelId: string;
  onActiveChannelChange: (id: string) => void;
}

/**
 * 임베딩 대상 선택기의 좌측 채널 목록.
 * Figma `17414:97989` 280×634 — 헤더 44 + 목록.
 *
 * 목록 `17414:97995`: `px 12`, 카운트와 리스트 사이 gap 6, 아이템 사이 gap 2.
 * 아이템 `17414:97999`: padding 12, gap 12, radius 8, 선택 시
 * `fill/primary/normal/neutral` 배경. 테두리는 없다.
 *
 * 여기서 고른 채널은 우측 상세의 강조 대상일 뿐 임베딩 선택이 아니다 —
 * 실제 선택은 우측 체크박스가 한다.
 */
export default function ChannelTalkChannelListPanel({
  channels,
  activeChannelId,
  onActiveChannelChange,
}: ChannelTalkChannelListPanelProps) {
  return (
    <div className="flex min-h-0 min-w-0 flex-col">
      <div className="border-line-normal-neutral shrink-0 border-b px-4 py-3">
        <p className="text-body-xsmall text-text-normal-alternative truncate">채널명</p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-1.5 px-3 pt-2">
        <p className="text-body-xsmall text-text-normal-assistive shrink-0 px-2">전체 {channels.length}개</p>

        <ul className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
          {channels.map((channel) => {
            const active = channel.id === activeChannelId;
            return (
              <li key={channel.id}>
                <button
                  type="button"
                  aria-current={active ? 'true' : undefined}
                  onClick={() => onActiveChannelChange(channel.id)}
                  className={cn(
                    'flex w-full cursor-pointer items-center gap-3 rounded-lg p-3 text-left transition-colors',
                    active ? 'bg-fill-primary-normal-neutral' : 'hover:bg-fill-normal-interaction-hover',
                  )}
                >
                  <ChannelTalkNameIcon kind="channel" />
                  <span className="text-body-small text-text-normal-neutral min-w-0 flex-1 truncate">
                    {channel.name}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
