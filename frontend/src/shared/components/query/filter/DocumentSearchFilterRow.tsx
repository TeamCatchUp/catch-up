'use client';

import type { DateRange } from 'react-day-picker';

import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

import DateFilterChip from './DateFilterChip';
import SmartFilterControl from './SmartFilterControl';
import SourceFilterDropdown from './SourceFilterDropdown';

export { default as SmartFilterStatusPill } from './SmartFilterStatusPill';

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
  const activeTriggerMaxWidthClassName = isResultExpanded ? 'max-w-55' : 'max-w-45';

  return (
    <div className={cn('flex items-center gap-5', isResultExpanded ? 'w-full px-2' : 'w-182', className)}>
      <div className={cn('flex min-w-0 shrink-0 items-center gap-2.5', isResultExpanded ? 'w-[459px]' : 'w-[385px]')}>
        <SourceFilterDropdown
          selectedSources={selectedSources}
          onSourcesChange={onSourcesChange}
          activeMaxWidthClassName={activeTriggerMaxWidthClassName}
          preserveInputFocus={preserveInputFocus}
          onOpenChange={onFilterOverlayOpenChange}
        />
        <DateFilterChip
          value={dateRange}
          onChange={onDateRangeChange}
          activeMaxWidthClassName={activeTriggerMaxWidthClassName}
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
