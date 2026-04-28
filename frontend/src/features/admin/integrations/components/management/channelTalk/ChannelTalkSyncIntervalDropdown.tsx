'use client';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconClock from '@/public/icons/icon/clock.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import { CHANNEL_TALK_SYNC_INTERVAL_LABELS, type ChannelTalkSyncInterval } from '../../../types/channelTalkModel';

const SYNC_INTERVAL_OPTIONS: ChannelTalkSyncInterval[] = ['5min', '15min', '30min', '1hour', '6hour', '24hour'];

const DEFAULT_SYNC_INTERVAL: ChannelTalkSyncInterval = '5min';

interface ChannelTalkSyncIntervalDropdownProps {
  value: ChannelTalkSyncInterval;
  onChange?: (next: ChannelTalkSyncInterval) => void;
}

/**
 * 채널톡 동기화 주기 dropdown — Default / Hover / Pressed(펼침) 3상태.
 *
 * Figma node mapping:
 * - Default: `12060:83652` (652×46) / `12060:84438` (604×46)
 * - Hover:   `12060:83662` / `12060:84449`
 * - Pressed: `12060:84298` (펼침 228h, 옵션 4개 가시) / `12060:84387`
 *
 * 부모 컨테이너의 width를 그대로 채움 (w-full). 메뉴는 trigger 폭과 동일하게 펼쳐짐.
 */
export default function ChannelTalkSyncIntervalDropdown({ value, onChange }: ChannelTalkSyncIntervalDropdownProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(
            'border-edge-neutral bg-fill-strong hover:bg-fill-interaction-hover data-[state=open]:bg-fill-interaction-pressed flex h-11.5 w-full cursor-pointer items-center gap-1.5 rounded-lg border p-3 transition-colors',
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <IconClock className="text-icon-normal size-5.5 shrink-0" />
            <span className="text-body-small text-content-neutral truncate">동기화 주기 설정</span>
          </div>
          <span className="text-body-small text-content-alternative shrink-0">
            {CHANNEL_TALK_SYNC_INTERVAL_LABELS[value]}
          </span>
          <IconArrowDown className="text-icon-normal size-6 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        sideOffset={2}
        align="start"
        className="bg-fill-normal w-[var(--radix-dropdown-menu-trigger-width)] min-w-0 rounded-lg border-0 p-1"
      >
        {SYNC_INTERVAL_OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option}
            onSelect={() => onChange?.(option)}
            className={cn(
              'text-body-small text-content-normal h-10 gap-2 px-2 py-2',
              option === value && 'bg-fill-interaction-hover',
            )}
          >
            <span className="flex-1 truncate">
              {CHANNEL_TALK_SYNC_INTERVAL_LABELS[option]}
              {option === DEFAULT_SYNC_INTERVAL && ' (기본)'}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
