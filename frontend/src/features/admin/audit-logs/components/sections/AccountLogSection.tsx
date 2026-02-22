'use client';

import { useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { INTEGRATION_ACCOUNTS } from '@/shared/constants/integrationAccounts';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import { ACTION_LABEL, SORT_OPTIONS, STATUS_BADGE_CLASS, STATUS_LABEL } from '../../constants/auditLogConfig';
import { auditLogsQueries } from '../../queries/auditLogs.queries';
import type { AuditLog, AuditLogTableRow, AuditSortKey } from '../../types/auditLog';

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
                  {SORT_OPTIONS.find((o) => o.key === sortKey)?.label}
                </span>
                <IconDropdownDown className="size-4.5 text-gray-50" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" sideOffset={2} className="w-30 min-w-0">
              {SORT_OPTIONS.map((option) => (
                <DropdownMenuItem
                  key={option.key}
                  onClick={() => setSortKey(option.key)}
                  className={cn(sortKey === option.key && 'bg-neutral-1')}
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

      {/* 테이블 + 디테일 패널 */}
      <div className="border-neutral-3 flex min-h-0 overflow-clip border-y" style={{ height: 558 }}>
        {/* 좌측: 테이블 */}
        <div className="border-neutral-3 flex min-w-0 flex-1 flex-col overflow-clip border-r bg-white">
          {/* 헤더 */}
          <div className="border-neutral-3 bg-neutral-1 flex h-9 shrink-0 items-center border-b px-5">
            <div className="grid flex-1 grid-cols-4 items-center gap-1">
              <span className="text-body-xsmall pl-7.5 text-left text-gray-50">이름</span>
              <span className="text-body-xsmall text-center text-gray-50">실행 일자</span>
              <span className="text-body-xsmall text-center text-gray-50">구분</span>
              <span className="text-body-xsmall text-center text-gray-50">상태</span>
            </div>
          </div>

          {/* 행 */}
          {tableRows.length === 0 ? (
            <div className="text-body-small flex h-full min-h-25 items-center justify-center text-gray-50">
              감사 로그가 없습니다.
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
              {tableRows.map((row) => {
                const isActive = activeKey === row.key;
                const badgeCls = STATUS_BADGE_CLASS[row.status] ?? 'bg-neutral-2 text-gray-50';
                const isSuccess = row.status === '성공';

                return (
                  <button
                    key={row.key}
                    type="button"
                    onClick={() => setActiveKey(row.key)}
                    className={cn(
                      'border-neutral-3 flex h-12.5 shrink-0 cursor-pointer items-center border-b px-5 text-left',
                      isActive ? 'bg-blue-1' : 'hover:bg-neutral-1 bg-white',
                    )}
                  >
                    <div className="grid flex-1 grid-cols-4 items-center gap-1">
                      {/* 이름 */}
                      <div className="flex items-center gap-4">
                        <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
                        <span className="text-body-small text-gray-80 truncate">{row.name}</span>
                      </div>

                      {/* 실행 일자 */}
                      <div className="flex items-center justify-center">
                        <span className="text-body-xsmall text-gray-80 truncate">{row.executedAt}</span>
                      </div>

                      {/* 구분 */}
                      <div className="flex items-center justify-center">
                        <span className="text-body-xsmall text-gray-80 truncate">{row.action}</span>
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
        <div className="flex min-w-0 flex-1 flex-col overflow-clip bg-white py-5 pl-6">
          {!selectedLog ? (
            <div className="text-body-small flex h-full items-center justify-center text-gray-50">
              선택된 로그 정보가 없습니다.
            </div>
          ) : (
            <div className="flex h-full flex-col gap-4">
              {/* 프로필 + 이름 */}
              <div className="flex items-center gap-3">
                <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
                <span className="text-heading-medium text-gray-80 truncate">{selectedLog.name}</span>
              </div>

              <div className="flex flex-col gap-9">
                {/* 기본 정보 */}
                <div className="text-body-small flex flex-col gap-2 tracking-tight">
                  <InfoRow label="메일" value={selectedLog.email} />
                  <InfoRow label="부서" value={selectedLog.department} />
                  <InfoRow label="직급" value={selectedLog.rank} />
                  <InfoRow label="가입일" value={formatDate(selectedLog.joinedAt)} />
                  <InfoRow label="승인자" value={selectedLog.approver} />
                </div>

                {/* 연동된 계정 정보 */}
                <IntegrationAccountsSection
                  name={selectedLog.name}
                  email={selectedLog.email}
                  accountIds={selectedLog.accountIds}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/** 정보 행 */
const InfoRow = ({ label, value }: { label: string; value: string }) => (
  <div className="flex w-full items-center gap-14">
    <span className="w-19.75 shrink-0 text-gray-50">{label}</span>
    <span className="text-gray-70 min-w-0 flex-1 truncate">{value}</span>
  </div>
);

/** 연동된 계정 정보 섹션 */
const IntegrationAccountsSection = ({
  name,
  email,
  accountIds,
}: {
  name: string;
  email: string;
  accountIds: Partial<Record<IntegrationService, string>>;
}) => (
  <div className="flex flex-col gap-2">
    <div className="flex items-center gap-2">
      <IconCloudCheckFilled className="text-gray-20 size-5" />
      <h3 className="text-heading-small text-gray-70">연동된 계정 정보</h3>
    </div>

    <div className="border-neutral-2 flex flex-col overflow-clip rounded-xl border">
      {INTEGRATION_ACCOUNTS.map((account, index) => {
        const accountId = accountIds[account.service];
        const isLinked = !!accountId;
        const iconClassName = account.service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

        return (
          <div
            key={account.service}
            className={cn(
              'border-neutral-2 flex h-15.75 shrink-0 items-center gap-5 overflow-clip px-4 py-2',
              index !== INTEGRATION_ACCOUNTS.length - 1 && 'border-b',
            )}
          >
            <div className="flex w-41.25 shrink-0 items-center gap-3">
              <account.Icon className={iconClassName} />
              <span className="text-body-small text-gray-80 truncate">{account.name}</span>
            </div>

            {isLinked ? (
              <div className="flex shrink-0 flex-col items-start justify-center gap-0.5">
                <div className="flex shrink-0 items-center gap-2.5">
                  <DefaultProfile className="border-neutral-2 text-gray-30 size-6.25 shrink-0 rounded-full border" />
                  <span className="text-body-xsmall text-gray-80 max-w-33.25 shrink-0 truncate">{name}</span>
                  <span className="rounded-md2 bg-neutral-2 text-body-xsmall shrink-0 px-1.5 py-0.5 tracking-tight text-gray-50">
                    {accountId}
                  </span>
                </div>
                <span className="text-body-xsmall shrink-0 truncate text-gray-50">{email}</span>
              </div>
            ) : (
              <div className="bg-neutral-1 flex w-[259px] shrink-0 items-center justify-center self-stretch rounded-lg">
                <div className="flex items-center gap-1">
                  <IconCloudOff className="size-6 text-gray-50" />
                  <span className="text-body-xsmall text-gray-50">연동 안됨</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  </div>
);

export default AccountLogSection;
