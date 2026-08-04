'use client';

import IconTagChannel from '@/public/icons/icon/tag_channel.svg';
import { cn } from '@/shared/utils/cn';

import EntityChip from '../EntityChip';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';

interface ChannelTalkChannelListPanelProps {
  channels: readonly ChannelTalkChannelTarget[];
  /** 우측 패널에 표시 중인 채널 ids — 임베딩 선택과 무관한 visibility state */
  visibleChannelIds: ReadonlySet<string>;
  onToggleVisibility: (channelId: string) => void;
}

/**
 * 임베딩 대상 선택기의 좌측 채널 목록.
 *
 * 여기서 켠 채널만 우측에 나온다. 임베딩 선택이 아니라 **표시 토글**이고,
 * 끄면 그 채널의 임베딩 선택도 함께 풀린다 — 구 모달(`ChannelList`)과 같은
 * 시맨틱이다.
 */
export default function ChannelTalkChannelListPanel({
  channels,
  visibleChannelIds,
  onToggleVisibility,
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
            const visible = visibleChannelIds.has(channel.id);
            return (
              <li key={channel.id}>
                <button
                  type="button"
                  aria-pressed={visible}
                  aria-label={`${channel.name} 표시 (해제 시 임베딩 선택도 함께 해제됨)`}
                  onClick={() => onToggleVisibility(channel.id)}
                  className={cn(
                    'flex w-full cursor-pointer items-center gap-3 rounded-lg p-3 text-left transition-colors',
                    visible ? 'bg-fill-primary-normal-neutral' : 'hover:bg-fill-normal-interaction-hover',
                  )}
                >
                  <EntityChip icon={IconTagChannel} />
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
