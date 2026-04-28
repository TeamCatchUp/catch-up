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
  CHANNEL_SYNC_INTERVAL_DEFAULT,
  CHANNEL_SYNC_INTERVAL_OPTIONS,
  CHANNEL_TALK_SYNC_INTERVAL_LABELS,
  type ChannelTalkSyncInterval,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
  DOCUMENT_SPACE_SYNC_INTERVAL_OPTIONS,
} from '../../../types/channelTalkModel';

/**
 * dropdown 옵션 셋 분기.
 * - `channel`: 5분(기본) / 15분 / 30분 / 1시간 — 실시간 대화 채널
 * - `documentSpace`: 1시간(기본) / 6시간 / 12시간 / 24시간 — 정적 문서
 */
type SyncIntervalDropdownVariant = 'channel' | 'documentSpace';

const VARIANT_OPTIONS: Record<SyncIntervalDropdownVariant, ChannelTalkSyncInterval[]> = {
  channel: CHANNEL_SYNC_INTERVAL_OPTIONS,
  documentSpace: DOCUMENT_SPACE_SYNC_INTERVAL_OPTIONS,
};

const VARIANT_DEFAULTS: Record<SyncIntervalDropdownVariant, ChannelTalkSyncInterval> = {
  channel: CHANNEL_SYNC_INTERVAL_DEFAULT,
  documentSpace: DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
};

interface ChannelTalkSyncIntervalDropdownProps {
  variant: SyncIntervalDropdownVariant;
  value: ChannelTalkSyncInterval;
  /** lock 상태 — 트리거 비활성 + 회색 배경 */
  disabled?: boolean;
  onChange?: (next: ChannelTalkSyncInterval) => void;
}

/**
 * 채널톡 동기화 주기 dropdown — Default / Hover / Pressed(펼침) 3상태.
 *
 * `variant`에 따라 옵션 셋 자동 분기. 부모 컨테이너의 width를 그대로 채움 (w-full).
 */
export default function ChannelTalkSyncIntervalDropdown({
  variant,
  value,
  disabled,
  onChange,
}: ChannelTalkSyncIntervalDropdownProps) {
  const options = VARIANT_OPTIONS[variant];
  const defaultValue = VARIANT_DEFAULTS[variant];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild disabled={disabled}>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            'border-edge-neutral flex h-11.5 w-full items-center gap-1.5 rounded-lg border p-3 transition-colors',
            disabled
              ? 'bg-fill-interaction-disable text-content-assistive cursor-not-allowed'
              : 'bg-fill-strong hover:bg-fill-interaction-hover data-[state=open]:bg-fill-interaction-pressed cursor-pointer',
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
        {options.map((option) => (
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
              {option === defaultValue && ' (기본)'}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
