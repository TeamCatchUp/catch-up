'use client';

import { useState } from 'react';

import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconPersonFilled from '@/public/icons/icon/person_filled.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';

import ReviewQueueFilterSearchPanel, { type ReviewQueueFilterOption } from './ReviewQueueFilterSearchPanel';

interface OwnerAddPopoverProps {
  /** 추가 후보 — 멤버 목록에서 현 담당자를 뺀 나머지다. id는 user_id 문자열이다 */
  candidates: readonly ReviewQueueFilterOption[];
  onAssign: (userIds: readonly number[]) => void;
}

/** 지정 확인 모달 문구. 지정은 검토 권한을 담당자에게 넘긴다 */
const ASSIGN_CONFIRM = {
  title: '담당자를 지정할까요?',
  description: '지정한 담당자가 이 문서의 검토를 맡게 됩니다. 지정 후에는 담당자만 판정하고 내보낼 수 있습니다.',
} as const;

/**
 * 담당자 카드 헤더의 + 버튼과 추가 드롭다운(400px) — 후보 검색·다중 선택 후
 * 확인 모달을 거쳐 지정을 내보낸다. 요청·토스트는 소비처 몫이다.
 */
export default function OwnerAddPopover({ candidates, onAssign }: OwnerAddPopoverProps) {
  const [open, setOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<readonly string[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  // 확인 모달이 열리면 팝오버가 바깥 상호작용으로 닫히며 선택이 비워진다 — 대상은 여기 미리 옮겨 둔다
  const [pendingIds, setPendingIds] = useState<readonly number[]>([]);

  const toggle = (optionId: string) =>
    setSelectedIds((prev) => (prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId]));

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setSelectedIds([]);
  };

  const openConfirm = () => {
    setPendingIds(selectedIds.map(Number));
    setConfirmOpen(true);
    handleOpenChange(false);
  };

  const confirmAssign = () => {
    onAssign(pendingIds);
  };

  return (
    <>
      <Popover open={open} onOpenChange={handleOpenChange}>
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <Button variant="icon-only-gray" size="sm" className="p-1" aria-label="담당자 추가하기">
                <IconAddSmall aria-hidden className="size-5" />
              </Button>
            </PopoverTrigger>
          </TooltipTrigger>
          {/* 우측 패널 끝의 버튼이라 툴팁은 좌측에 세운다. 아이콘+제목 구성은 시안 확정분 */}
          <TooltipContent side="left" className="flex items-center gap-1.5">
            <IconAddSmall aria-hidden className="size-5" />
            담당자 추가하기
          </TooltipContent>
        </Tooltip>

        <PopoverContent align="end" className="shadow-modal flex w-100 flex-col gap-3 p-0 pb-3">
          {/* 헤더 우측의 가이드 링크는 노드 간 문구가 갈려(X9) 보류한다 — 임의 선택 금지 */}
          <div className="border-line-normal-assistive border-b px-4 py-2">
            <span className="text-body-small text-text-normal-alternative">담당자 추가하기</span>
          </div>

          <ReviewQueueFilterSearchPanel
            options={candidates}
            selectedIds={selectedIds}
            onToggle={toggle}
            placeholder="담당자 검색"
            OptionIcon={IconPersonFilled}
            trailingAction={
              <Button
                variant="box-solid-primary"
                size="lg"
                className="h-10 shrink-0 self-start"
                disabled={selectedIds.length === 0}
                onClick={openConfirm}
              >
                추가하기
              </Button>
            }
          />
        </PopoverContent>
      </Popover>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={ASSIGN_CONFIRM.title}
        description={ASSIGN_CONFIRM.description}
        onConfirm={confirmAssign}
      />
    </>
  );
}
