'use client';

import { memo } from 'react';

import IconTag from '@/public/icons/icon/tag.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';
import { cn } from '@/shared/utils/cn';

import type { ChannelTalkChannel } from '../../../../utils/mapChannelTalkSyncTargets';
import EntityChip from './EntityChip';

interface ChannelListProps {
  channels: ChannelTalkChannel[];
  // 우측 패널에 표시 중인 채널 ids — 임베딩 선택과 무관한 visibility state
  visibleChannelIds: Set<string>;
  // 전체 선택 상태 (visibility + 모든 채널 + 모든 스페이스가 모두 선택됨)
  isAllSelected: boolean;
  onToggleVisibility: (channelId: string) => void;
  onToggleAll: () => void;
}

function ChannelList({ channels, visibleChannelIds, isAllSelected, onToggleVisibility, onToggleAll }: ChannelListProps) {
  return (
    <div className="border-edge-neutral flex w-85 flex-col border-r">
      <div className="flex flex-col gap-3 px-4 pt-4">
        <div className="flex h-7 items-center justify-between">
          <span className="text-heading-medium text-content-strong pl-2">채널</span>
          <button
            type="button"
            onClick={onToggleAll}
            className="flex cursor-pointer items-center gap-1"
            aria-label="채널 전체 선택"
          >
            <CheckboxIcon checked={isAllSelected} className="size-5" />
            <span className="text-body-xsmall text-content-normal whitespace-nowrap">전체 선택하기</span>
          </button>
        </div>
        <span className="text-body-xsmall text-content-alternative pl-2">전체 {channels.length}개</span>
      </div>

      <ul className="custom-scrollbar flex flex-1 flex-col gap-1 overflow-y-auto px-4 pt-1.5 pb-4">
        {channels.map((channel) => {
          const isVisible = visibleChannelIds.has(channel.channel_id);
          return (
            <li key={channel.channel_id}>
              <button
                type="button"
                onClick={() => onToggleVisibility(channel.channel_id)}
                className={cn(
                  'flex h-14 w-full cursor-pointer items-center gap-1.5 rounded-lg px-1 transition-colors',
                  isVisible ? 'bg-fill-primary-normal-neutral' : 'hover:bg-fill-strong',
                )}
                aria-pressed={isVisible}
                aria-label={`${channel.display_name} 표시`}
              >
                <EntityChip icon={IconTag} />
                <span className="text-body-small text-content-normal line-clamp-1 min-w-0 flex-1 text-left">
                  {channel.display_name}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default memo(ChannelList);
