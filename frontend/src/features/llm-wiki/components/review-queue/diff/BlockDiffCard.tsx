'use client';

import { useState } from 'react';

import IconDropdownDown from '@/public/icons/icon/dropdown_down.svg';
import IconDropdownUp from '@/public/icons/icon/dropdown_up.svg';
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
}

/**
 * 블록 변경 1건 = 카드 1장 (Figma 17848:106171 계열).
 *
 * 본문 배치는 kind가 정한다 — modified는 좌우 비교, added/removed는 단일 전폭
 * (시안의 "없는 쪽은 안 그린다" 문법, removed는 added의 거울상으로 프론트가 확정).
 * 시안의 연필·순환화살표 아이콘과 카드 직접 수정 버튼은 뺐다 — 순환화살표는 되돌리기 중복이고,
 * 블록 단위 편집 진입은 디자인 미정이라 추후 작업이다.
 */
export default function BlockDiffCard({
  entry,
  defaultCollapsed = false,
  onApprove,
  onRevert,
  onDelete,
}: BlockDiffCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const { id, kind, title, before, after, reason } = entry;
  const ChevronIcon = collapsed ? IconDropdownDown : IconDropdownUp;

  return (
    <section className="border-line-normal-neutral rounded-xl border p-4">
      <header className="flex w-full items-center gap-2">
        <Button
          variant="icon-only-gray"
          size="sm"
          aria-expanded={!collapsed}
          aria-label={collapsed ? '펼치기' : '접기'}
          onClick={() => setCollapsed((value) => !value)}
        >
          <ChevronIcon aria-hidden className="size-5" />
        </Button>
        <h3 className="text-heading-medium text-text-normal-normal min-w-0 flex-1 truncate">{title}</h3>
        <Button variant="box-outline-gray" size="sm" onClick={() => onDelete(id)}>
          삭제
        </Button>
        <Button variant="box-outline-gray" size="sm" onClick={() => onRevert(id)}>
          되돌리기
        </Button>
        <Button variant="box-solid-primary" size="sm" onClick={() => onApprove(id)}>
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
