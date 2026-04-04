'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import { cn } from '@/shared/utils/cn';

import { CATEGORY_LABEL, STATUS_BADGE_CLASS, STATUS_LABEL } from '../../constants/auditLogConfig';
import { auditLogsQueries } from '../../queries/auditLogs.queries';
import { useAuditIntegrationFilterStore } from '../../store/auditIntegrationFilterStore';
import type { AuditIntegrationLog } from '../../types/auditIntegrationLogModel';
import { formatDate } from '../../utils/formatDate';
import AuditLogFilterBar from '../AuditLogFilterBar';
import ApiCallDetail from '../integration/ApiCallDetail';
import { getServiceIconCls, ServiceIcon } from '../integration/Helpers';
import SyncIntegrationDetail from '../integration/SyncIntegrationDetail';

/** 연동 감사 로그 섹션 */
export default function IntegrationLogSection() {
  const { data: logs = [] } = useQuery(auditLogsQueries.integrations());

  const {
    sort: sortKey,
    setSort: setSortKey,
    searchTerm,
    setSearchTerm,
    dateRange,
    setDateRange,
  } = useAuditIntegrationFilterStore();
  const [activeKey, setActiveKey] = useState<string | null>(null);

  /* 검색 + 날짜 범위 필터 + 정렬 */
  const sorted = useMemo(
    () =>
      logs
        .filter((l) => {
          if (searchTerm && !l.userName.includes(searchTerm)) return false;
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
        })
        .toSorted((a, b) => {
          const diff = new Date(b.executedAt).getTime() - new Date(a.executedAt).getTime();
          return sortKey === 'newest' ? diff : -diff;
        }),
    [logs, searchTerm, dateRange, sortKey],
  );

  /* 선택된 로그 데이터 */
  const selectedLog: AuditIntegrationLog | null = sorted.find((l) => l.logId === activeKey) ?? null;

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
        <div className="border-edge-neutral bg-fill-normal flex min-w-0 flex-1 flex-col overflow-clip border-r">
          {/* 헤더 */}
          <div className="border-edge-neutral bg-fill-strong text-body-xsmall text-content-alternative flex h-9 shrink-0 items-center gap-1 border-b px-5">
            <span className="w-13.75 shrink-0">커넥터</span>
            <span className="min-w-25 flex-1 text-center">실행 일자</span>
            <span className="flex-1 text-center">구분</span>
            <span className="w-32 min-w-32 text-center">이용자</span>
            <span className="flex-1 text-center">상태</span>
          </div>

          {/* 행 */}
          {sorted.length === 0 ? (
            <div className="text-body-small text-content-alternative flex h-full min-h-25 items-center justify-center">
              연동 로그가 없습니다.
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
              {sorted.map((log) => {
                const isActive = activeKey === log.logId;
                const statusLabel = STATUS_LABEL[log.status];
                const badgeCls =
                  STATUS_BADGE_CLASS[statusLabel] ?? 'bg-fill-interaction-hover text-content-alternative';
                const isSuccess = log.status === 'success';
                const iconCls = getServiceIconCls(log.service);

                return (
                  <button
                    key={log.logId}
                    type="button"
                    onClick={() => setActiveKey(log.logId)}
                    className={cn(
                      'border-edge-neutral flex h-12.5 shrink-0 cursor-pointer items-center gap-1 border-b px-5 text-left',
                      isActive ? 'bg-fill-primary-assistive' : 'hover:bg-fill-strong bg-fill-normal',
                    )}
                  >
                    {/* 커넥터 */}
                    <div className="flex w-13.75 shrink-0 items-center">
                      <div className="bg-fill-strong border-edge-neutral flex items-center justify-center rounded-full border p-1">
                        <ServiceIcon service={log.service} className={iconCls} />
                      </div>
                    </div>

                    {/* 실행 일자 */}
                    <div className="text-body-xsmall text-content-normal min-w-25 flex-1 truncate text-center">
                      {formatDate(log.executedAt)}
                    </div>

                    {/* 구분 */}
                    <div className="text-body-xsmall text-content-normal flex-1 truncate text-center">
                      {CATEGORY_LABEL[log.category]}
                    </div>

                    {/* 이용자 */}
                    <div className="flex w-32 min-w-32 items-center justify-center gap-1.5">
                      <DefaultProfile className="text-content-assistive size-6.25 shrink-0 rounded-full" />
                      <span className="text-body-xsmall text-content-normal truncate">{log.userName}</span>
                    </div>

                    {/* 상태 */}
                    <div className="flex flex-1 items-center justify-center">
                      <span
                        className={cn(
                          'rounded-md2 text-body-xsmall inline-flex shrink-0 items-center gap-1 px-1.5 py-0.5',
                          badgeCls,
                        )}
                      >
                        {isSuccess ? <IconCheckCircle className="size-4" /> : <IconDelete2 className="size-4" />}
                        {statusLabel}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 우측: 디테일 패널 */}
        <div className="bg-fill-normal flex min-w-0 flex-1 flex-col overflow-y-auto py-5 pl-6">
          {!selectedLog ? (
            <div className="text-body-small text-content-alternative flex h-full items-center justify-center">
              선택된 로그 정보가 없습니다.
            </div>
          ) : selectedLog.category === 'api_call' ? (
            <ApiCallDetail log={selectedLog} />
          ) : (
            <SyncIntegrationDetail log={selectedLog} />
          )}
        </div>
      </div>
    </div>
  );
}
