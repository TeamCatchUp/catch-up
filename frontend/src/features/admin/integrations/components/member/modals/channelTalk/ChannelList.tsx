'use client';

import IconTag from '@/public/icons/icon/tag.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';
import { cn } from '@/shared/utils/cn';

import EntityChip from './EntityChip';
import type { ChannelTalkChannel } from './mockChannels';

interface ChannelListProps {
  channels: ChannelTalkChannel[];
  selectedChannelIds: Set<string>;
  onToggleChannel: (channelId: string) => void;
  onToggleAll: () => void;
}

export default function ChannelList({ channels, selectedChannelIds, onToggleChannel, onToggleAll }: ChannelListProps) {
  const isAllSelected = channels.length > 0 && channels.every((channel) => selectedChannelIds.has(channel.channel_id));

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

      <ul className="custom-scrollbar flex flex-1 flex-col overflow-y-auto px-4 pt-1.5 pb-4">
        {channels.map((channel) => {
          const isSelected = selectedChannelIds.has(channel.channel_id);
          return (
            <li key={channel.channel_id}>
              <button
                type="button"
                onClick={() => onToggleChannel(channel.channel_id)}
                className={cn(
                  'flex h-14 w-full cursor-pointer items-center gap-1.5 rounded-lg px-1 transition-colors',
                  isSelected ? 'bg-fill-primary-normal-neutral' : 'hover:bg-fill-strong',
                )}
              >
                <CheckboxIcon checked={isSelected} className="size-6" />
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
