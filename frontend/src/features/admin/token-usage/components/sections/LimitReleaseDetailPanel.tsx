'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';

import IconArrowOutward from '@/public/icons/icon/arrow_outward.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import { Input } from '@/shared/components/ui/input';
import { Separator } from '@/shared/components/ui/separator';

import { DEFAULT_DAILY_LIMIT, DEFAULT_MONTHLY_LIMIT } from '../../constants/tokenUsageConfig';
import type { LimitReleaseRequest } from '../../types/tokenUsage';

/** 정보 행 (label w-28 = 112px, gap-14 = 56px) */
const InfoRow = ({ label, value }: { label: string; value: string }) => (
  <div className="text-body-small flex w-full items-center gap-14">
    <span className="w-28 shrink-0 text-content-alternative">{label}</span>
    <span className="text-content-neutral min-w-0 flex-1 truncate">{value}</span>
  </div>
);

interface LimitReleaseDetailPanelProps {
  request: LimitReleaseRequest;
  onApprove: (id: string, grantAmount: number) => void;
  onReject: (id: string) => void;
}

const LimitReleaseDetailPanel = ({ request, onApprove, onReject }: LimitReleaseDetailPanelProps) => {
  const [grantAmount, setGrantAmount] = useState('');
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);

  const handleApprove = () => {
    const amount = Number(grantAmount);
    if (!grantAmount || isNaN(amount) || amount <= 0) {
      toast.error('추가 토큰 부여량을 입력해주세요.');
      return;
    }
    setApproveDialogOpen(true);
  };

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto">
      {/* 프로필 헤더 + 액션 버튼 */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-5">
          <div className="flex flex-1 items-center gap-3">
            <DefaultProfile className="border-edge-assistive text-content-assistive size-7 shrink-0 rounded-full border" />
            <span className="text-heading-medium text-content-normal truncate">{request.name}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2.5">
            <Button variant="box-outline-gray" size="md" onClick={() => setRejectDialogOpen(true)}>
              반려
            </Button>
            <Button variant="box-outline-gray" size="md" onClick={handleApprove}>
              승인
            </Button>
          </div>
        </div>

        {/* 정보 섹션 */}
        <div className="text-body-small flex flex-col gap-4 tracking-tight">
          {/* 기본 정보 */}
          <div className="flex flex-col gap-2">
            <InfoRow label="메일" value={request.email} />
            <InfoRow label="부서" value={request.team} />
            <InfoRow label="직급" value={request.position} />
          </div>

          {/* 신청 정보 */}
          <div className="flex flex-col gap-2">
            <InfoRow label="추가 토큰 신청 사유" value={request.reason} />
            <InfoRow label="추가 토큰 신청량" value={`${request.requestedAmount}$`} />
          </div>
        </div>
      </div>

      {/* 추가 토큰 부여량 입력 */}
      <div className="flex items-center gap-18">
        <span className="text-body-small shrink-0 text-content-alternative">추가 토큰 부여량</span>
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <Input
            inputSize="lg"
            type="number"
            placeholder="토큰 금액"
            value={grantAmount}
            onChange={(e) => setGrantAmount(e.target.value)}
            className="min-w-0 flex-1"
          />
          <span className="text-body-small shrink-0 text-content-alternative">$</span>
        </div>
      </div>

      {/* 설정 카드 영역 */}
      <div className="flex flex-col gap-3">
        {/* 개인 토큰 사용 제한 설정 카드 */}
        <div className="bg-fill-strong border-edge-assistive flex flex-col gap-2.5 rounded-lg border px-3 py-2.5">
          <div className="flex items-center justify-between">
            <span className="text-heading-small text-content-neutral">설정된 개인 토큰 사용 제한 설정</span>
            <Link
              href="/admin/token-usage?tab=user-management"
              className="border-edge-neutral rounded-md2 flex h-7 items-center gap-1 border bg-fill-normal px-1.5 py-1"
            >
              <IconArrowOutward className="size-6 text-content-alternative" />
              <span className="text-body-xsmall text-content-alternative">수정 페이지 바로가기</span>
            </Link>
          </div>
          <Separator />
          <div className="text-body-small flex flex-col gap-1 tracking-tight">
            <div className="flex items-center justify-between">
              <span className="text-content-alternative">하루 최대 토큰 비용</span>
              <span className="text-content-neutral">
                {request.dailyLimit === DEFAULT_DAILY_LIMIT
                  ? `${request.dailyLimit} $ (기본값)`
                  : `${request.dailyLimit} $`}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-content-alternative">월 최대 토큰 비용</span>
              <span className="text-content-neutral">
                {request.monthlyLimit === DEFAULT_MONTHLY_LIMIT
                  ? `${request.monthlyLimit} $ (기본값)`
                  : `${request.monthlyLimit} $`}
              </span>
            </div>
          </div>
        </div>

        {/* 사용자 토큰 사용량 분석 카드 */}
        <div className="bg-fill-strong border-edge-assistive flex items-center justify-between rounded-lg border px-3 py-2.5">
          <span className="text-heading-small text-content-neutral">사용자 토큰 사용량 분석</span>
          <Link
            href="/admin/token-usage?tab=org-usage"
            className="border-edge-neutral rounded-md2 flex h-7 items-center gap-1 border bg-fill-normal px-1.5 py-1"
          >
            <IconArrowOutward className="size-6 text-content-alternative" />
            <span className="text-body-xsmall text-content-alternative">페이지 바로가기</span>
          </Link>
        </div>
      </div>

      {/* 반려 확인 다이얼로그 */}
      <ConfirmDialog
        open={rejectDialogOpen}
        onOpenChange={setRejectDialogOpen}
        title="요청을 반려하시겠습니까?"
        description={`${request.name}님의 토큰 추가 요청(${request.requestedAmount}$)을 반려합니다.`}
        confirmLabel="반려"
        variant="danger"
        onConfirm={() => onReject(request.id)}
      />

      {/* 승인 확인 다이얼로그 */}
      <ConfirmDialog
        open={approveDialogOpen}
        onOpenChange={setApproveDialogOpen}
        title="요청을 승인하시겠습니까?"
        description={`${request.name}님에게 ${grantAmount}$의 추가 토큰을 부여합니다.`}
        confirmLabel="승인"
        variant="blue"
        onConfirm={() => onApprove(request.id, Number(grantAmount))}
      />
    </div>
  );
};

export default LimitReleaseDetailPanel;
