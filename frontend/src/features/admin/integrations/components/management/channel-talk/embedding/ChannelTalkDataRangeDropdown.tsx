'use client';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

interface ChannelTalkDataRangeDropdownProps {
  value: string;
  options: readonly string[];
  onChange: (next: string) => void;
  /** 접근성 라벨 — 행마다 같은 드롭다운이 반복되므로 대상 이름을 넣는다 */
  label: string;
}

/**
 * 임베딩 대상의 데이터 기간 선택.
 * Figma `17449:111883`(채널) · `17449:111894`(도큐먼트) — 같은 Dropdown 인스턴스다.
 * h36, px 10 / py 8, gap 6, radius 8, `min-w 36` / `max-w 150`.
 *
 * 스텝 ①의 {@link ChannelTalkSyncIntervalDropdown}과 다른 물건이다 — 저건
 * h46에 시계 아이콘이 붙는 풀폭 트리거다.
 *
 * 선택지 목록은 Figma에 "1개월"·"전체" 두 값만 보여서 근거가 없다. 배선 단계에서
 * 실제 옵션이 정해질 때까지 호출부가 넘긴다.
 */
export default function ChannelTalkDataRangeDropdown({
  value,
  options,
  onChange,
  label,
}: ChannelTalkDataRangeDropdownProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`${label} 데이터 기간`}
          className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-interaction-hover data-[state=open]:bg-fill-normal-interaction-pressed flex h-9 max-w-37.5 min-w-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-2 transition-colors"
        >
          <span className="text-body-small text-text-normal-neutral min-w-0 flex-1 truncate text-left">{value}</span>
          <IconDropdownDown className="text-icon-normal-neutral size-4 shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        sideOffset={2}
        align="end"
        className="bg-fill-normal-normal min-w-32 rounded-lg border-0 p-1"
      >
        {options.map((option) => (
          <DropdownMenuItem
            key={option}
            onSelect={() => onChange(option)}
            className={cn(
              'text-body-small text-text-normal-normal h-10 gap-2 px-2 py-2',
              option === value && 'bg-fill-normal-interaction-hover',
            )}
          >
            <span className="flex-1 truncate">{option}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
