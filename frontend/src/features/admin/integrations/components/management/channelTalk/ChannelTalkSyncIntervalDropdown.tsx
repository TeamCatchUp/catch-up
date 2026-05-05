'use client';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconClock from '@/public/icons/icon/clock_dropdown.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import {
  CHANNEL_TALK_SYNC_INTERVAL_LABELS,
  type ChannelTalkSyncInterval,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
  DOCUMENT_SPACE_SYNC_INTERVAL_OPTIONS,
} from '../../../types/channelTalkModel';

interface ChannelTalkSyncIntervalDropdownProps {
  value: ChannelTalkSyncInterval;
  /** lock 상태 — 트리거 비활성 + 회색 배경 */
  disabled?: boolean;
  onChange?: (next: ChannelTalkSyncInterval) => void;
}

/**
 * 채널톡 도큐먼트 스페이스 동기화 주기 dropdown — Default / Hover / Pressed(펼침) 3상태.
 *
 * 정적 문서 특성에 맞춘 1시간 / 6시간 / 12시간 / 24시간 옵션. 부모 컨테이너 width 풀폭.
 */
export default function ChannelTalkSyncIntervalDropdown({
  value,
  disabled,
  onChange,
}: ChannelTalkSyncIntervalDropdownProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild disabled={disabled}>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            'border-edge-neutral flex h-11.5 w-full items-center gap-1.5 rounded-lg border p-3 transition-colors',
            disabled
              ? 'bg-fill-interaction-disable cursor-not-allowed'
              : 'bg-fill-strong hover:bg-fill-interaction-hover data-[state=open]:bg-fill-interaction-pressed cursor-pointer',
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <IconClock className={cn('size-5.5 shrink-0', disabled ? 'text-icon-alternative' : 'text-icon-normal')} />
            <span
              className={cn('text-body-small truncate', disabled ? 'text-content-assistive' : 'text-content-neutral')}
            >
              동기화 주기 설정
            </span>
          </div>
          <span
            className={cn('text-body-small shrink-0', disabled ? 'text-content-assistive' : 'text-content-alternative')}
          >
            {CHANNEL_TALK_SYNC_INTERVAL_LABELS[value]}
          </span>
          <IconArrowDown className={cn('size-6 shrink-0', disabled ? 'text-icon-alternative' : 'text-icon-normal')} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        sideOffset={2}
        align="start"
        className="bg-fill-normal w-[var(--radix-dropdown-menu-trigger-width)] min-w-0 rounded-lg border-0 p-1"
      >
        {DOCUMENT_SPACE_SYNC_INTERVAL_OPTIONS.map((option) => (
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
              {option === DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT && ' (기본)'}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
