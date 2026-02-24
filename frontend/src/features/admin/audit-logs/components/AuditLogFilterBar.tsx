import type { DateRange } from 'react-day-picker';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import { SORT_OPTIONS } from '../constants/auditLogConfig';
import type { AuditSortKey } from '../types/auditLog';

interface AuditLogFilterBarProps {
  sortKey: AuditSortKey;
  onSortChange: (key: AuditSortKey) => void;
  dateRange: DateRange | undefined;
  onDateRangeChange: (range: DateRange | undefined) => void;
  searchTerm: string;
  onSearchTermChange: (term: string) => void;
}

/** 감사 로그 공통 필터바 (정렬 + 날짜 범위 + 검색) */
const AuditLogFilterBar = ({
  sortKey,
  onSortChange,
  dateRange,
  onDateRangeChange,
  searchTerm,
  onSearchTermChange,
}: AuditLogFilterBarProps) => (
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-2">
      {/* 정렬 드롭다운 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="border-neutral-3 flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border bg-white px-2.5 py-2"
          >
            <span className="text-body-small text-gray-70">{SORT_OPTIONS.find((o) => o.key === sortKey)?.label}</span>
            <IconDropdownDown className="size-4.5 text-gray-50" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" sideOffset={2} className="w-30 min-w-0">
          {SORT_OPTIONS.map((option) => (
            <DropdownMenuItem
              key={option.key}
              onClick={() => onSortChange(option.key)}
              className={cn(sortKey === option.key && 'bg-neutral-1')}
            >
              {option.label}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* 날짜 범위 선택 */}
      <DateRangePicker value={dateRange} onChange={onDateRangeChange} />
    </div>

    {/* 검색 */}
    <label className="bg-neutral-1 border-neutral-2 flex h-10 w-70 items-center gap-1.5 rounded-lg border px-3 py-2">
      <IconSearch className="text-gray-30 size-5 shrink-0" />
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => onSearchTermChange(e.target.value)}
        placeholder="질문, 키워드로 검색하세요."
        className="text-body-small text-gray-70 placeholder:text-gray-30 w-full bg-transparent outline-none"
      />
    </label>
  </div>
);

export default AuditLogFilterBar;
