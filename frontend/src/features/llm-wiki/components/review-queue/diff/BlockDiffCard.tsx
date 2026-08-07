'use client';

import { useState } from 'react';

import IconArrowDropdownDown from '@/public/icons/icon/arrow_dropdown_down.svg';
import IconArrowDropdownRight from '@/public/icons/icon/arrow_dropdown_right.svg';
import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import DiffText from './DiffText';

export interface BlockDiffCardProps {
  entry: BlockDiffEntry;
  defaultCollapsed?: boolean;
  onApprove: (id: string) => void;
  onRevert: (id: string) => void;
  onDelete: (id: string) => void;
  /** 이 블록만 편집 — 진입 후 UI는 디자인 미정이라 콜백만 뚫어 둔다 */
  onEditRequest: (id: string) => void;
}

/**
 * 블록 변경 1건 = 카드 1장 (Figma 17849:106310 헤더 배치 기준).
 *
 * 본문 배치는 kind가 정한다 — modified는 좌우 비교, added/removed는 단일 전폭
 * (시안의 "없는 쪽은 안 그린다" 문법, removed는 added의 거울상으로 프론트가 확정).
 */
export default function BlockDiffCard({
  entry,
  defaultCollapsed = false,
  onApprove,
  onRevert,
  onDelete,
  onEditRequest,
}: BlockDiffCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const { id, kind, title, before, after, reason } = entry;
  // 접힘 → 오른쪽, 펼침 → 아래. disclosure triangle 관례이자 시안의 icon/arrow_drop_down(6413:79613) 계열이다
  const ChevronIcon = collapsed ? IconArrowDropdownRight : IconArrowDropdownDown;

  return (
    <section className="border-line-normal-neutral rounded-xl border p-4">
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
        <Button
          variant="icon-only-gray"
          size="sm"
          className="size-7"
          aria-label="되돌리기"
          onClick={() => onRevert(id)}
        >
          <IconRotate aria-hidden className="size-5" />
        </Button>
        {/* 높이를 박는 이유: outline은 1px 테두리가 더해져 28→30이고 solid는 28이라 나란히 두면 어긋난다.
            공용 Button의 특성이라 리포 관례(pending/page.tsx)대로 양쪽에 같은 높이를 준다 */}
        <Button variant="box-outline-gray" size="sm" className="h-7.5" onClick={() => onDelete(id)}>
          삭제
        </Button>
        <Button variant="box-solid-primary" size="sm" className="h-7.5" onClick={() => onApprove(id)}>
          승인
        </Button>
      </header>

      {!collapsed && (
        <>
          <div className={cn('mt-3 flex gap-5', kind !== 'modified' && 'flex-col')}>
            {before && <DiffText lines={before} tone="removed" />}
            {after && <DiffText lines={after} tone="added" />}
          </div>
          {reason && (
            <div className="bg-fill-normal-strong mt-3 flex flex-col gap-2 rounded-xl px-4 py-3">
              <span className="text-body-xsmall text-text-normal-alternative">수정된 이유</span>
              <p className="text-body-small text-text-normal-neutral">{reason}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
