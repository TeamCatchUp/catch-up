'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import Pagination from '@/shared/components/ui/pagination';

import { auditLogsQueries } from '../../queries/auditLogs.queries';
import { useAuditQuestionFilterStore } from '../../store/auditQuestionFilterStore';
import { formatDate } from '../../utils/formatDate';
import AuditLogFilterBar from '../AuditLogFilterBar';

const PAGE_SIZE = 15;

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
      <AuditLogFilterBar
        sortKey={sort}
        onSortChange={setSort}
        dateRange={dateRange}
        onDateRangeChange={setDateRange}
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
      />

      {/* 테이블 + 페이지네이션 */}
      <div className="flex flex-col gap-14">
        <div className="border-edge-neutral flex flex-col overflow-clip border-r">
          {/* 헤더 */}
          <div className="border-edge-neutral bg-fill-strong flex h-9 shrink-0 items-center border-b px-5">
            <div className="grid flex-1 grid-cols-3 items-center gap-1">
              <span className="text-body-xsmall pl-7.5 text-left text-content-alternative">이름</span>
              <span className="text-body-xsmall text-center text-content-alternative">실행 일자</span>
              <span className="text-body-xsmall text-center text-content-alternative">질문</span>
            </div>
          </div>

          {/* 행 */}
          {pageItems.length === 0 ? (
            <div className="text-body-small flex h-80 items-center justify-center text-content-alternative">
              질문 로그가 없습니다.
            </div>
          ) : (
            <div className="flex flex-col">
              {pageItems.map((log) => (
                <Link
                  key={log.logId}
                  href={`/admin/question-logs/${log.messageId}?userId=${log.userId}&from=audit-logs`}
                  className="border-edge-neutral hover:bg-fill-strong flex h-12.5 shrink-0 items-center border-b px-5 transition-colors"
                >
                  <div className="grid flex-1 grid-cols-3 items-center gap-1">
                    {/* 이름 */}
                    <div className="flex items-center gap-4">
                      <DefaultProfile className="border-edge-assistive text-content-assistive size-7 shrink-0 rounded-full border" />
                      <span className="text-body-small text-content-normal truncate">{log.name}</span>
                    </div>

                    {/* 실행 일자 */}
                    <div className="flex items-center justify-center">
                      <span className="text-body-xsmall text-content-normal truncate">{formatDate(log.executedAt)}</span>
                    </div>

                    {/* 질문 */}
                    <div className="flex items-center justify-center">
                      <span className="text-body-xsmall text-content-normal truncate">{log.query}</span>
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
