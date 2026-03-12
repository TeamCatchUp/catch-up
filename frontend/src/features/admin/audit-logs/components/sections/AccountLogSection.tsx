'use client';

import { useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import { cn } from '@/shared/utils/cn';

import { ACTION_LABEL, STATUS_BADGE_CLASS, STATUS_LABEL } from '../../constants/auditLogConfig';
import { auditLogsQueries } from '../../queries/auditLogs.queries';
import type { AuditLog, AuditLogTableRow, AuditSortKey } from '../../types/auditLog';
import { formatDate } from '../../utils/formatDate';
import AccountDetailPanel from '../account/AccountDetailPanel';
import AuditLogFilterBar from '../AuditLogFilterBar';

/** 계정관리 감사 로그 섹션 */
const AccountLogSection = () => {
  const { data: logs = [] } = useQuery(auditLogsQueries.list());
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<AuditSortKey>('newest');
  const [searchTerm, setSearchTerm] = useState('');
  const [dateRange, setDateRange] = useState<DateRange | undefined>();

  /* 검색 + 날짜 범위 필터 */
  const filtered = useMemo(
    () =>
      logs.filter((l) => {
        if (!l.name.includes(searchTerm)) return false;
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
      return sortKey === 'newest' ? diff : -diff;
    });
    return arr;
  }, [filtered, sortKey]);

  /* 테이블 행 변환 */
  const tableRows: AuditLogTableRow[] = useMemo(
    () =>
      sorted.map((l) => ({
        key: l.logId,
        name: l.name,
        picture: l.picture,
        executedAt: formatDate(l.executedAt),
        action: ACTION_LABEL[l.action],
        status: STATUS_LABEL[l.status],
      })),
    [sorted],
  );

  /* 선택된 로그 데이터 */
  const selectedLog: AuditLog | null = sorted.find((l) => l.logId === activeKey) ?? null;

  return (
    <div className="flex w-full flex-col gap-3">
      {/* 필터바 */}
      <AuditLogFilterBar
        sortKey={sortKey}
        onSortChange={setSortKey}
        dateRange={dateRange}
        onDateRangeChange={setDateRange}
        searchTerm={searchTerm}
        onSearchTermChange={setSearchTerm}
      />

      {/* 테이블 + 디테일 패널 */}
      <div className="border-edge-neutral flex min-h-0 overflow-clip border-y" style={{ height: 558 }}>
        {/* 좌측: 테이블 */}
        <div className="border-edge-neutral flex min-w-0 flex-1 flex-col overflow-clip border-r bg-fill-normal">
          {/* 헤더 */}
          <div className="border-edge-neutral bg-fill-strong flex h-9 shrink-0 items-center border-b px-5">
            <div className="grid flex-1 grid-cols-4 items-center gap-1">
              <span className="text-body-xsmall pl-7.5 text-left text-content-alternative">이름</span>
              <span className="text-body-xsmall text-center text-content-alternative">실행 일자</span>
              <span className="text-body-xsmall text-center text-content-alternative">구분</span>
              <span className="text-body-xsmall text-center text-content-alternative">상태</span>
            </div>
          </div>

          {/* 행 */}
          {tableRows.length === 0 ? (
            <div className="text-body-small flex h-full min-h-25 items-center justify-center text-content-alternative">
              감사 로그가 없습니다.
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
              {tableRows.map((row) => {
                const isActive = activeKey === row.key;
                const badgeCls = STATUS_BADGE_CLASS[row.status] ?? 'bg-fill-interaction-hover text-content-alternative';
                const isSuccess = row.status === '성공';

                return (
                  <button
                    key={row.key}
                    type="button"
                    onClick={() => setActiveKey(row.key)}
                    className={cn(
                      'border-edge-neutral flex h-12.5 shrink-0 cursor-pointer items-center border-b px-5 text-left',
                      isActive ? 'bg-fill-primary-assistive' : 'hover:bg-fill-strong bg-fill-normal',
                    )}
                  >
                    <div className="grid flex-1 grid-cols-4 items-center gap-1">
                      {/* 이름 */}
                      <div className="flex items-center gap-4">
                        <DefaultProfile className="text-content-assistive size-7 shrink-0 rounded-full" />
                        <span className="text-body-small text-content-normal truncate">{row.name}</span>
                      </div>

                      {/* 실행 일자 */}
                      <div className="flex items-center justify-center">
                        <span className="text-body-xsmall text-content-normal truncate">{row.executedAt}</span>
                      </div>

                      {/* 구분 */}
                      <div className="flex items-center justify-center">
                        <span className="text-body-xsmall text-content-normal truncate">{row.action}</span>
                      </div>

                      {/* 상태 */}
                      <div className="flex items-center justify-center">
                        <span
                          className={cn(
                            'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center gap-1 px-1.5 py-0.5',
                            badgeCls,
                          )}
                        >
                          {isSuccess ? <IconCheckCircle className="size-4" /> : <IconDelete2 className="size-4" />}
                          {row.status}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 우측: 디테일 패널 */}
        <div className="flex min-w-0 flex-1 flex-col overflow-clip bg-fill-normal py-5 pl-6">
          {!selectedLog ? (
            <div className="text-body-small flex h-full items-center justify-center text-content-alternative">
              선택된 로그 정보가 없습니다.
            </div>
          ) : (
            <AccountDetailPanel log={selectedLog} />
          )}
        </div>
      </div>
    </div>
  );
};

export default AccountLogSection;
