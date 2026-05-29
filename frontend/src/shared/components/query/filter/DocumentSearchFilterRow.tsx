'use client';

import { useMemo, useRef, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { format } from 'date-fns';

import IconCalendar from '@/public/icons/icon/calendar.svg';
import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconDropdownUp from '@/public/icons/icon/dropdown_up.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconInfoFilled from '@/public/icons/icon/info_filled.svg';
import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

import { Button } from '../../ui/button';
import { DateRangePicker } from '../../ui/date-range-picker';
import { Popover, PopoverContent, PopoverTrigger } from '../../ui/popover';
import { Switch } from '../../ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../ui/tooltip';

interface SourceOption {
  value: DocsSource;
  label: string;
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

interface FilterTriggerButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active: boolean;
  label: string;
  valueLabel?: string;
  open?: boolean;
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

interface SourceFilterDropdownProps {
  selectedSources: DocsSource[];
  onSourcesChange: (next: DocsSource[]) => void;
  preserveInputFocus?: boolean;
  onOpenChange?: (open: boolean) => void;
}

interface DateFilterChipProps {
  value: DateRange | undefined;
  onChange: (next: DateRange | undefined) => void;
  preserveInputFocus?: boolean;
  onOpenChange?: (open: boolean) => void;
}

interface SmartFilterControlProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  className?: string;
  description: string;
  tone: 'primary' | 'neutral';
}

interface SmartFilterStatusPillProps {
  enabled: boolean;
  onApplyClick?: () => void;
}

interface DocumentSearchFilterRowProps {
  className?: string;
  variant?: 'entry' | 'result-expanded';
  selectedSources: DocsSource[];
  onSourcesChange: (next: DocsSource[]) => void;
  dateRange: DateRange | undefined;
  onDateRangeChange: (next: DateRange | undefined) => void;
  smartFilter: boolean;
  onSmartFilterChange: (next: boolean) => void;
  preserveInputFocus?: boolean;
  onFilterOverlayOpenChange?: (open: boolean) => void;
}

const SOURCE_OPTIONS: readonly SourceOption[] = [
  { value: 'github', label: 'Github', Icon: GitHub },
  { value: 'channel_talk', label: '채널톡', Icon: ChannelTalk },
  { value: 'confluence', label: 'Confluence', Icon: Confluence },
  { value: 'jira', label: 'Jira', Icon: Jira },
  { value: 'slack', label: 'Slack', Icon: Slack },
];

const SOURCE_LABELS = new Map(SOURCE_OPTIONS.map((source) => [source.value, source.label]));

function FilterTriggerButton({
  active,
  label,
  valueLabel,
  open,
  Icon,
  className,
  onMouseDown,
  ...props
}: FilterTriggerButtonProps) {
  const DropdownIcon = open ? IconDropdownUp : IconDropdownDown;

  return (
    <button
      type="button"
      onMouseDown={onMouseDown}
      className={cn(
        'flex h-9 min-w-0 cursor-pointer items-center justify-center gap-2 rounded-lg border px-2.5 py-1.5 transition-colors',
        active
          ? 'border-edge-primary bg-fill-primary-assistive text-content-primary'
          : 'border-edge-neutral bg-fill-normal text-content-normal hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed',
        className,
      )}
      {...props}
    >
      <Icon className={cn('size-5 shrink-0', active ? 'text-icon-primary' : 'text-icon-normal')} />
      {active ? (
        <>
          <span className="text-body-small shrink-0 font-medium whitespace-nowrap">{label}:</span>
          <span className="text-body-small min-w-0 truncate font-medium">{valueLabel}</span>
        </>
      ) : (
        <span className="text-body-small shrink-0 font-medium whitespace-nowrap">{label}</span>
      )}
      <DropdownIcon className={cn('size-5 shrink-0', active ? 'text-icon-primary' : 'text-icon-normal')} />
    </button>
  );
}

function SourceFilterDropdown({
  selectedSources,
  onSourcesChange,
  preserveInputFocus,
  onOpenChange,
}: SourceFilterDropdownProps) {
  const [open, setOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedLabels = selectedSources.map((source) => SOURCE_LABELS.get(source) ?? source);
  const filteredOptions = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase();
    return SOURCE_OPTIONS.filter((option) => {
      if (selectedSources.includes(option.value)) return false;
      if (!normalized) return true;
      return option.label.toLowerCase().includes(normalized);
    });
  }, [searchTerm, selectedSources]);

  const toggleSource = (source: DocsSource) => {
    if (selectedSources.includes(source)) {
      onSourcesChange(selectedSources.filter((selected) => selected !== source));
      return;
    }
    onSourcesChange([...selectedSources, source]);
  };

  const clearSelected = () => {
    setSearchTerm('');
    onSourcesChange([]);
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange} modal={false}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          active={selectedSources.length > 0}
          label="검색 범위"
          valueLabel={selectedLabels.join(', ')}
          open={open}
          Icon={IconFile}
          aria-label="검색 범위 필터"
          className={cn(selectedSources.length > 0 && 'max-w-55')}
          onMouseDown={preserveInputFocus ? (event) => event.preventDefault() : undefined}
        />
      </PopoverTrigger>
      <PopoverContent
        data-document-search-filter-popover
        align="start"
        sideOffset={8}
        className="border-edge-strong bg-fill-normal flex max-h-72 w-75 flex-col gap-3 rounded-2xl border px-0 py-2.5 shadow-[0px_4px_15px_rgba(0,0,0,0.16)]"
        onMouseDown={(event) => event.stopPropagation()}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        <div className="w-full px-2.5">
          <div
            role="button"
            tabIndex={-1}
            className={cn(
              'bg-fill-strong focus-within:border-edge-primary flex w-full cursor-text items-start gap-1.5 overflow-hidden rounded-lg border-[1.5px] border-transparent px-3 py-2',
              selectedSources.length > 0 ? 'max-h-60 min-h-10' : 'h-10',
            )}
            onClick={() => inputRef.current?.focus()}
          >
            <div className="flex min-w-0 flex-1 flex-col gap-1.5 overflow-y-auto">
              {selectedSources.length > 0 && (
                <div className="flex w-full flex-wrap gap-1.5">
                  {selectedSources.map((source) => {
                    const option = SOURCE_OPTIONS.find((item) => item.value === source);
                    if (!option) return null;
                    return (
                      <span
                        key={source}
                        className="border-edge-strong bg-fill-normal flex h-[37px] items-center gap-1 rounded-full border px-1.5 py-1.5"
                      >
                        <span className="flex min-w-0 items-center gap-1.5 px-1">
                          <option.Icon className="size-5 shrink-0" />
                          <span className="text-body-small text-content-normal max-w-[150px] truncate">
                            {option.label}
                          </span>
                        </span>
                        <button
                          type="button"
                          aria-label={`${option.label} 제거`}
                          className="text-icon-neutral hover:bg-fill-interaction-hover flex size-[22px] cursor-pointer items-center justify-center rounded-full"
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={(event) => {
                            event.stopPropagation();
                            toggleSource(source);
                          }}
                        >
                          <IconCancelSmall className="size-4.5" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}
              <div className="flex min-w-0 items-center">
                <input
                  ref={inputRef}
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="협업툴 검색하기"
                  className="text-body-small placeholder:text-content-assistive h-[23px] min-w-0 flex-1 bg-transparent outline-none"
                />
              </div>
            </div>
            {(searchTerm || selectedSources.length > 0) && (
              <button
                type="button"
                aria-label="검색 범위 필터 초기화"
                className="text-icon-neutral hover:bg-fill-interaction-hover flex size-[23px] shrink-0 cursor-pointer items-center justify-center rounded-full"
                onMouseDown={(event) => event.preventDefault()}
                onClick={(event) => {
                  event.stopPropagation();
                  clearSelected();
                }}
              >
                <IconCancelSmall className="size-5" />
              </button>
            )}
          </div>
        </div>

        <ul
          className={cn(
            'flex shrink-0 flex-col gap-1 overflow-y-auto px-1.5',
            filteredOptions.length === 0 && 'min-h-20 items-center justify-center',
          )}
        >
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option) => (
              <li key={option.value}>
                <button
                  type="button"
                  className="hover:bg-fill-interaction-hover active:bg-fill-interaction-pressed flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl px-2 py-1 transition-colors"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => toggleSource(option.value)}
                >
                  <span className="border-edge-neutral bg-fill-strong flex size-[34px] shrink-0 items-center justify-center rounded-full border p-1.5">
                    <option.Icon className="size-5 shrink-0" />
                  </span>
                  <span className="text-body-small text-content-normal min-w-0 flex-1 truncate text-left">
                    {option.label}
                  </span>
                </button>
              </li>
            ))
          ) : (
            <li className="text-body-small text-content-alternative px-2 text-center">검색 결과가 없습니다.</li>
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

function formatDateRangeLabel(range: DateRange | undefined): string | undefined {
  if (!range?.from) return undefined;
  const from = format(range.from, 'yyyy년 M월 d일');
  const to = format(range.to ?? range.from, 'yyyy년 M월 d일');
  return from === to ? from : `${from} - ${to}`;
}

function DateFilterChip({ value, onChange, preserveInputFocus, onOpenChange }: DateFilterChipProps) {
  const [open, setOpen] = useState(false);
  const valueLabel = formatDateRangeLabel(value);
  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <DateRangePicker
      value={value}
      onChange={onChange}
      align="start"
      onOpenChange={handleOpenChange}
      contentProps={{ 'data-document-search-filter-popover': true }}
      trigger={
        <FilterTriggerButton
          active={Boolean(valueLabel)}
          label="날짜"
          valueLabel={valueLabel}
          open={open}
          Icon={IconCalendar}
          aria-label="날짜 필터"
          className={cn(valueLabel && 'max-w-55')}
          onMouseDown={preserveInputFocus ? (event) => event.preventDefault() : undefined}
        />
      }
    />
  );
}

function SmartFilterControl({ checked, onCheckedChange, className, description, tone }: SmartFilterControlProps) {
  return (
    <div
      className={cn(
        'flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-2.5',
        tone === 'primary' ? 'bg-fill-primary-normal-neutral' : 'bg-fill-strong',
        className,
      )}
    >
      <div className="flex items-center gap-2.5">
        <TooltipProvider delayDuration={150}>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" aria-label="스마트 필터 설명" className="text-icon-neutral cursor-help">
                <IconInfoFilled className="size-4.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" sideOffset={8} size="sm">
              <p>따로 설정하지 않아도 괜찮아요.</p>
              <p>&apos;이번 주 컨플루언스 문서&apos;처럼 검색하면</p>
              <p>자동으로 필터가 적용돼요.</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <span className="text-body-xsmall text-content-alternative font-medium whitespace-nowrap">{description}</span>
      </div>
      <span aria-hidden className="bg-edge-neutral h-4 w-px shrink-0" />
      <label className="flex cursor-pointer items-center gap-2.5 px-0.5">
        <span className="text-body-xsmall text-content-normal font-medium whitespace-nowrap">스마트 필터</span>
        <Switch checked={checked} onCheckedChange={onCheckedChange} aria-label="스마트 필터" />
      </label>
    </div>
  );
}

export function SmartFilterStatusPill({ enabled, onApplyClick }: SmartFilterStatusPillProps) {
  if (enabled) {
    return (
      <div className="bg-fill-strong flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-2.5">
        <IconInfoFilled className="text-icon-neutral size-4.5 shrink-0" />
        <span className="text-body-xsmall text-content-neutral font-medium whitespace-nowrap">스마트 필터 적용됨</span>
      </div>
    );
  }

  return (
    <div className="bg-fill-strong flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-2.5">
      <div className="flex items-center gap-2.5">
        <IconInfoFilled className="text-icon-neutral size-4.5 shrink-0" />
        <span className="text-body-xsmall text-content-alternative font-medium whitespace-nowrap">기본 검색 결과</span>
      </div>
      <span aria-hidden className="bg-edge-neutral h-4 w-px shrink-0" />
      <Button type="button" variant="text-primary-blue" size="sm" onClick={onApplyClick} className="px-1.5 py-1">
        스마트 필터 적용하기
      </Button>
    </div>
  );
}

export default function DocumentSearchFilterRow({
  className,
  variant = 'entry',
  selectedSources,
  onSourcesChange,
  dateRange,
  onDateRangeChange,
  smartFilter,
  onSmartFilterChange,
  preserveInputFocus = false,
  onFilterOverlayOpenChange,
}: DocumentSearchFilterRowProps) {
  const isResultExpanded = variant === 'result-expanded';

  return (
    <div className={cn('flex items-center gap-5', isResultExpanded ? 'w-full px-2' : 'w-182', className)}>
      <div className={cn('flex min-w-0 shrink-0 items-center gap-2.5', isResultExpanded ? 'w-[459px]' : 'w-[385px]')}>
        <SourceFilterDropdown
          selectedSources={selectedSources}
          onSourcesChange={onSourcesChange}
          preserveInputFocus={preserveInputFocus}
          onOpenChange={onFilterOverlayOpenChange}
        />
        <DateFilterChip
          value={dateRange}
          onChange={onDateRangeChange}
          preserveInputFocus={preserveInputFocus}
          onOpenChange={onFilterOverlayOpenChange}
        />
      </div>
      <SmartFilterControl
        checked={smartFilter}
        onCheckedChange={onSmartFilterChange}
        className={isResultExpanded ? 'w-[385px]' : 'w-[323px]'}
        description={isResultExpanded ? '필터를 직접 안 눌러도 자동으로 적용돼요' : '자동으로 적용되는 검색 필터'}
        tone={isResultExpanded ? 'neutral' : 'primary'}
      />
    </div>
  );
}
