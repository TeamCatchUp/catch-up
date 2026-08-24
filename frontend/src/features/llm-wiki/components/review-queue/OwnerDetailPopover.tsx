'use client';

import { type ReactNode, useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';

interface OwnerDetailPopoverProps {
  /** 해제 대상 담당자 표시명 — 헤더 문구에 그대로 박힌다 */
  name: string;
  /** 본문에 다시 그릴 담당자 행. 트리거와 같은 시각을 소비처가 넘긴다 */
  row: ReactNode;
  onRemove: () => void;
  /** 팝오버를 여는 트리거(담당자 행 버튼) */
  children: ReactNode;
}

/** 담당자 행에서 여는 해제 팝오버(300px) — 해제는 관리자 전용이라 소비처가 노출을 거른다. */
export default function OwnerDetailPopover({ name, row, onRemove, children }: OwnerDetailPopoverProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent align="start" className="shadow-tooltip w-75 rounded-xl p-0">
        <div className="bg-fill-normal-strong border-line-normal-assistive border-b px-4 py-2">
          <span className="text-body-xsmall text-text-normal-alternative">{name} 님이 이 문서의 검토 담당자입니다</span>
        </div>
        <div className="flex flex-col gap-2.5 p-4">
          {row}
          <Button
            variant="box-outline-gray"
            size="md"
            className="h-9 w-full"
            onClick={() => {
              onRemove();
              setOpen(false);
            }}
          >
            담당자 해제하기
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
