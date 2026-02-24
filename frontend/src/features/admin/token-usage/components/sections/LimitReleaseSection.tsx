'use client';

import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconInventory from '@/public/icons/icon/inventory.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import { Separator } from '@/shared/components/ui/separator';
import { cn } from '@/shared/utils/cn';

import { POSITION_BADGE_CLASS, TEAM_BADGE_CLASS } from '../../constants/tokenUsageConfig';
import { tokenUsageQueries } from '../../queries/tokenUsage.queries';
import type { LimitReleaseRequest, LimitReleaseTableRow } from '../../types/tokenUsage';
import LimitReleaseDetailPanel from './LimitReleaseDetailPanel';

/** 제한 해제 요청 섹션 */
const LimitReleaseSection = () => {
  const { data: requests = [] } = useQuery(tokenUsageQueries.limitReleaseRequests());

  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [processedIds, setProcessedIds] = useState<Set<string>>(() => new Set());
  const [rejectAllDialogOpen, setRejectAllDialogOpen] = useState(false);
  const [approveAllDialogOpen, setApproveAllDialogOpen] = useState(false);

  /* 처리되지 않은 요청만 표시 */
  const pendingRequests = useMemo(
    () => requests.filter((r) => !processedIds.has(r.id)),
    [requests, processedIds],
  );

  /* 테이블 행 변환 */
  const tableRows: LimitReleaseTableRow[] = useMemo(
    () =>
      pendingRequests.map((r) => ({
        key: r.id,
        name: r.name,
        profileImage: r.profileImage,
        cost: r.cost,
        requestedAmount: r.requestedAmount,
        position: r.position,
        team: r.team,
      })),
    [pendingRequests],
  );

  /* 선택된 요청 */
  const selectedRequest: LimitReleaseRequest | null =
    pendingRequests.find((r) => r.id === activeKey) ?? null;

  const handleApprove = useCallback((id: string, grantAmount: number) => {
    setProcessedIds((prev) => new Set(prev).add(id));
    setActiveKey((prev) => (prev === id ? null : prev));
    toast.success(`${grantAmount}$ 토큰이 승인되었습니다.`);
  }, []);

  const handleReject = useCallback((id: string) => {
    setProcessedIds((prev) => new Set(prev).add(id));
    setActiveKey((prev) => (prev === id ? null : prev));
    toast.success('요청이 반려되었습니다.');
  }, []);

  const handleApproveAll = () => {
    const ids = pendingRequests.map((r) => r.id);
    setProcessedIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.add(id));
      return next;
    });
    setActiveKey(null);
    toast.success(`${ids.length}건의 요청이 전체 승인되었습니다.`);
  };

  const handleRejectAll = () => {
    const ids = pendingRequests.map((r) => r.id);
    setProcessedIds((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => next.add(id));
      return next;
    });
    setActiveKey(null);
    toast.success(`${ids.length}건의 요청이 전체 반려되었습니다.`);
  };

  return (
    <div className="flex w-full flex-col gap-3">
      {/* 헤더 + 도구모음 */}
      <div className="flex items-end justify-between">
        {/* 제목 + 설명 */}
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2.5">
            <span className="text-heading-large text-gray-80">토큰 추가 요청 신청 목록</span>
            <span className="text-heading-large text-blue-55">{pendingRequests.length}</span>
          </div>
          <span className="text-body-small text-gray-50">
            토큰 사용량을 초과한 임직원의 토큰 추가 신청을 확인하고 승인 여부를 결정해주세요.
          </span>
        </div>

        {/* 도구모음 */}
        <div className="flex items-center gap-2.5">
          {/* 전체 반려/승인 버튼 그룹 */}
          <div className="border-neutral-3 flex h-9 items-center gap-0.5 rounded-lg border bg-white px-2 py-0.5">
            <Button
              variant="text-secondary-mono"
              size="md"
              onClick={() => setRejectAllDialogOpen(true)}
              disabled={pendingRequests.length === 0}
            >
              전체 반려하기
            </Button>
            <Separator orientation="vertical" className="mx-0.5 h-6" />
            <Button
              variant="text-secondary-mono"
              size="md"
              onClick={() => setApproveAllDialogOpen(true)}
              disabled={pendingRequests.length === 0}
            >
              전체 승인하기
            </Button>
          </div>

          {/* 선택하기 버튼 */}
          <Button variant="box-outline-gray" size="md">
            선택하기
          </Button>

          {/* 아이콘 버튼 */}
          <Button variant="icon-outline-gray" size="md">
            <IconInventory className="size-6" />
          </Button>
        </div>
      </div>

      {/* 테이블 + 디테일 패널 */}
      <div className="border-neutral-3 flex min-h-0 overflow-clip border-y" style={{ height: 558 }}>
        {/* 좌측: 테이블 */}
        <div className="border-neutral-3 flex min-w-0 flex-1 flex-col overflow-clip border-r bg-white">
          {/* 테이블 헤더 */}
          <div className="border-neutral-3 bg-neutral-1 flex h-9 shrink-0 items-center border-b px-5">
            <div className="grid flex-1 grid-cols-3 items-center gap-1">
              <span className="text-body-xsmall pl-7.5 text-left text-gray-50">이름</span>
              <div className="text-body-xsmall flex items-center gap-1 text-center text-gray-50">
                <span className="flex-1">사용량</span>
                <span className="flex-1">추가 신청량</span>
              </div>
              <div className="text-body-xsmall flex items-center gap-1 text-center text-gray-50">
                <span className="flex-1">직급</span>
                <span className="flex-1">부서</span>
              </div>
            </div>
          </div>

          {/* 테이블 행 */}
          {tableRows.length === 0 ? (
            <div className="text-body-small flex h-full min-h-25 items-center justify-center text-gray-50">
              제한 해제 요청이 없습니다.
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col overflow-x-clip overflow-y-auto">
              {tableRows.map((row) => {
                const isActive = activeKey === row.key;

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
                    <div className="grid flex-1 grid-cols-3 items-center gap-1">
                      {/* 이름 */}
                      <div className="flex items-center gap-4">
                        <DefaultProfile className="border-neutral-2 text-gray-30 size-7 shrink-0 rounded-full border" />
                        <span className="text-body-small text-gray-80 truncate">{row.name}</span>
                      </div>

                      {/* 사용량 + 추가 신청량 */}
                      <div className="flex items-center gap-1">
                        <span className="text-body-small flex-1 text-center text-gray-70">
                          {row.cost} $
                        </span>
                        <span className="text-body-small flex-1 text-center text-gray-70">
                          {row.requestedAmount} $
                        </span>
                      </div>

                      {/* 직급 + 부서 */}
                      <div className="flex items-center gap-1">
                        <div className="flex flex-1 justify-center">
                          <span
                            className={cn(
                              'rounded-md2 text-body-xsmall truncate px-1.5 py-0.5',
                              POSITION_BADGE_CLASS[row.position] ?? 'bg-neutral-2 text-gray-50',
                            )}
                          >
                            {row.position}
                          </span>
                        </div>
                        <div className="flex flex-1 justify-center">
                          <span
                            className={cn(
                              'rounded-md2 text-body-xsmall truncate px-1.5 py-0.5',
                              TEAM_BADGE_CLASS,
                            )}
                          >
                            {row.team}
                          </span>
                        </div>
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
          {!selectedRequest ? (
            <div className="text-body-small flex h-full items-center justify-center text-gray-50">
              선택된 요청 정보가 없습니다.
            </div>
          ) : (
            <LimitReleaseDetailPanel
              key={selectedRequest.id}
              request={selectedRequest}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          )}
        </div>
      </div>

      {/* 전체 반려 확인 다이얼로그 */}
      <ConfirmDialog
        open={rejectAllDialogOpen}
        onOpenChange={setRejectAllDialogOpen}
        title="전체 요청을 반려하시겠습니까?"
        description={`${pendingRequests.length}건의 토큰 추가 요청을 모두 반려합니다.`}
        confirmLabel="전체 반려"
        variant="danger"
        onConfirm={handleRejectAll}
      />

      {/* 전체 승인 확인 다이얼로그 */}
      <ConfirmDialog
        open={approveAllDialogOpen}
        onOpenChange={setApproveAllDialogOpen}
        title="전체 요청을 승인하시겠습니까?"
        description={`${pendingRequests.length}건의 토큰 추가 요청을 신청량 그대로 모두 승인합니다.`}
        confirmLabel="전체 승인"
        variant="blue"
        onConfirm={handleApproveAll}
      />
    </div>
  );
};

export default LimitReleaseSection;
