'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import Pagination from '@/shared/components/ui/pagination';
import { cn } from '@/shared/utils/cn';

import { SORT_OPTIONS } from '../../constants/auditLogConfig';
import { auditLogsQueries } from '../../queries/auditLogs.queries';
import { useAuditQuestionFilterStore } from '../../store/auditQuestionFilterStore';

const PAGE_SIZE = 15;

/** 날짜 포맷: "2026.01.01. 10:32" */
const formatDate = (iso: string) => {
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${y}.${m}.${day}. ${h}:${min}`;
};

/** 감사 로그 — 질문 탭 섹션 */
const QuestionLogSection = () => {
  const { data: logs = [] } = useQuery(auditLogsQueries.questions());

  const sort = useAuditQuestionFilterStore((s) => s.sort);
  const setSort = useAuditQuestionFilterStore((s) => s.setSort);
  const dateRange = useAuditQuestionFilterStore((s) => s.dateRange);
  const setDateRange = useAuditQuestionFilterStore((s) => s.setDateRange);
  const searchTerm = useAuditQuestionFilterStore((s) => s.searchTerm);
  const setSearchTerm = useAuditQuestionFilterStore((s) => s.setSearchTerm);
  const currentPage = useAuditQuestionFilterStore((s) => s.currentPage);
  const setCurrentPage = useAuditQuestionFilterStore((s) => s.setCurrentPage);

  /* 검색 + 날짜 범위 필터 */
  const filtered = useMemo(
    () =>
      logs.filter((l) => {
        if (searchTerm && !l.query.includes(searchTerm) && !l.name.includes(searchTerm)) return false;
        if (dateRange?.from) {
          const d = new Date(l.executedAt);
          if (d < dateRange.from) return false;
          if (dateRange.to) {
            const endOfDay = new Date(dateRange.to);
            endOfDay.setHours(23, 59, 59, 999);
            if (d > endOfDay) return false;
          }
        }
        return true;
      }),
    [logs, searchTerm, dateRange],
  );

  /* 정렬 */
  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const diff = new Date(b.executedAt).getTime() - new Date(a.executedAt).getTime();
      return sort === 'newest' ? diff : -diff;
    });
    return arr;
  }, [filtered, sort]);

  /* 페이지네이션 */
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return sorted.slice(start, start + PAGE_SIZE);
  }, [sorted, currentPage]);

  return (
    <div className="flex w-full flex-col gap-3">
      {/* 필터바 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* 정렬 드롭다운 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="border-neutral-3 flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border bg-white px-2.5 py-2"
              >
                <span className="text-body-small text-gray-70">
                  {SORT_OPTIONS.find((o) => o.key === sort)?.label}
                </span>
                <IconDropdownDown className="size-4.5 text-gray-50" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" sideOffset={2} className="w-30 min-w-0">
              {SORT_OPTIONS.map((option) => (
                <DropdownMenuItem
                  key={option.key}
                  onClick={() => setSort(option.key)}
                  className={cn(sort === option.key && 'bg-neutral-1')}
                >
                  {option.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 날짜 범위 선택 */}
          <DateRangePicker value={dateRange} onChange={setDateRange} />
        </div>

        {/* 검색 */}
        <label className="bg-neutral-1 border-neutral-2 flex h-10 w-70 items-center gap-1.5 rounded-lg border px-3 py-2">
          <IconSearch className="text-gray-30 size-5 shrink-0" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="질문, 키워드로 검색하세요."
            className="text-body-small text-gray-70 placeholder:text-gray-30 w-full bg-transparent outline-none"
          />
        </label>
      </div>

      {/* 테이블 + 페이지네이션 */}
      <div className="flex flex-col gap-14">
        <div className="border-neutral-3 flex flex-col overflow-clip border-r">
          {/* 헤더 */}
          <div className="border-neutral-3 bg-neutral-1 flex h-9 shrink-0 items-center border-b px-5">
            <div className="grid flex-1 grid-cols-3 items-center gap-1">
              <span className="text-body-xsmall pl-7.5 text-left text-gray-50">이름</span>
              <span className="text-body-xsmall text-center text-gray-50">실행 일자</span>
              <span className="text-body-xsmall text-center text-gray-50">질문</span>
            </div>
          </div>

          {/* 행 */}
          {pageItems.length === 0 ? (
            <div className="text-body-small flex h-80 items-center justify-center text-gray-50">
              질문 로그가 없습니다.
            </div>
          ) : (
            <div className="flex flex-col">
              {pageItems.map((log) => (
                <Link
                  key={log.logId}
                  href={`/admin/question-logs/${log.messageId}?userId=${log.userId}&from=audit-logs`}
                  className="border-neutral-3 hover:bg-neutral-1 flex h-12.5 shrink-0 items-center border-b px-5 transition-colors"
                >
                  <div className="grid flex-1 grid-cols-3 items-center gap-1">
                    {/* 이름 */}
                    <div className="flex items-center gap-4">
                      <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
                      <span className="text-body-small text-gray-80 truncate">{log.name}</span>
                    </div>

                    {/* 실행 일자 */}
                    <div className="flex items-center justify-center">
                      <span className="text-body-xsmall text-gray-80 truncate">{formatDate(log.executedAt)}</span>
                    </div>

                    {/* 질문 */}
                    <div className="flex items-center justify-center">
                      <span className="text-body-xsmall text-gray-80 truncate">{log.query}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* 페이지네이션 */}
        {sorted.length > 0 && (
          <div className="flex items-center justify-center">
            <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
          </div>
        )}
      </div>
    </div>
  );
};

export default QuestionLogSection;
