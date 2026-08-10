'use client';

import { useState } from 'react';

import IconArrowDropdownDown from '@/public/icons/icon/arrow_dropdown_down.svg';
import IconArrowDropdownRight from '@/public/icons/icon/arrow_dropdown_right.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import DeletedBlockPanel from './DeletedBlockPanel';
import DiffText from './DiffText';

export interface BlockDiffCardProps {
  entry: BlockDiffEntry;
  defaultCollapsed?: boolean;
  onApprove: (id: string) => void;
  /** 제안 기각. 백엔드 RejectRequest와 같은 판정이다 */
  onReject: (id: string) => void;
  /** 이 블록만 편집 — 진입 후 UI는 디자인 미정이라 콜백만 뚫어 둔다 */
  onEditRequest: (id: string) => void;
}

/**
 * 블록 변경 1건 = 카드 1장 (Figma 펼침 17849:106310 · 접힘 17942:106488 · 반려됨 17942:106687).
 *
 * 본문 배치는 kind가 정한다 — modified는 좌우 비교, added는 초록 단일,
 * removed는 삭제 고지가 붙은 빨강 단일(DeletedBlockPanel).
 * 판정은 승인·반려 둘뿐이다. 되돌리기(rotate)는 반려와 겹쳐서 8/7에 빠졌다.
 */
export default function BlockDiffCard({
  entry,
  defaultCollapsed = false,
  onApprove,
  onReject,
  onEditRequest,
}: BlockDiffCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const { id, kind, title, before, after, reason, rejected = false } = entry;
  const ChevronIcon = collapsed ? IconArrowDropdownRight : IconArrowDropdownDown;

  return (
    <section className="border-line-normal-neutral flex flex-col gap-4 rounded-xl border px-5 py-4">
      <header className="flex w-full items-center gap-2">
        <Button
          variant="icon-only-gray"
          size="sm"
          className="size-7"
          aria-expanded={!collapsed}
          aria-label={collapsed ? '펼치기' : '접기'}
          onClick={() => setCollapsed((value) => !value)}
        >
          <ChevronIcon aria-hidden className="size-5" />
        </Button>
        <h3 className="text-heading-medium text-text-normal-normal min-w-0 flex-1 truncate">{title}</h3>

        {rejected ? (
          // Figma는 Box Button state=Inactive를 배지로 썼지만, 누를 수 없는 표시라 span으로 낸다.
          // 토큰은 그 Inactive 변형과 같은 것을 쓴다.
          <span className="bg-fill-normal-interaction-inactive border-line-normal-normal text-body-xsmall text-text-normal-assistive flex h-7.5 shrink-0 items-center gap-1 rounded-lg border px-2">
            <IconDelete2 aria-hidden className="text-icon-normal-assistive size-5" />
            반려됨
          </span>
        ) : (
          <>
            {/* 전역 "직접 수정"(섹션 헤더)과 구분하려고 라벨을 블록 단위로 좁혔다 */}
            <Button
              variant="icon-only-gray"
              size="sm"
              className="size-7"
              aria-label="이 블록 수정"
              onClick={() => onEditRequest(id)}
            >
              <IconEditPencil aria-hidden className="size-5" />
            </Button>
            {/* 높이를 박는 이유: outline은 1px 테두리가 더해져 28→30이고 solid는 28이라 나란히 두면 어긋난다.
                공용 Button의 특성이라 리포 관례(pending/page.tsx)대로 양쪽에 같은 높이를 준다 */}
            <Button variant="box-outline-gray" size="sm" className="h-7.5" onClick={() => onReject(id)}>
              반려
            </Button>
            <Button variant="box-solid-primary" size="sm" className="h-7.5" onClick={() => onApprove(id)}>
              승인
            </Button>
          </>
        )}
      </header>

      {!collapsed && (
        <>
          {kind === 'removed' && before ? (
            <DeletedBlockPanel lines={before} />
          ) : (
            <div className={cn('flex gap-5', kind !== 'modified' && 'flex-col')}>
              {before && <DiffText lines={before} tone="removed" />}
              {after && <DiffText lines={after} tone="added" />}
            </div>
          )}
          {reason && (
            <div className="bg-fill-normal-strong flex flex-col gap-2 rounded-xl px-4 py-3">
              <span className="text-body-xsmall text-text-normal-alternative">수정된 이유</span>
              <p className="text-body-small text-text-normal-neutral">{reason}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
