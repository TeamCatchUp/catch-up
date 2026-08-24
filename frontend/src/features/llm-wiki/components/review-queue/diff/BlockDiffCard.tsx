'use client';

import { type ComponentType, type SVGProps, useState } from 'react';

import IconArrowDropdownDown from '@/public/icons/icon/arrow_dropdown_down.svg';
import IconArrowDropdownRight from '@/public/icons/icon/arrow_dropdown_right.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import DeletedBlockPanel from './DeletedBlockPanel';
import DiffText from './DiffText';

export interface BlockDiffCardProps {
  entry: BlockDiffEntry;
  defaultCollapsed?: boolean;
  /** [BE] can_review. false면 판정 버튼을 렌더하지 않는다 — 열람은 그대로다 */
  canReview?: boolean;
  /** 반려 진입점. 사유 입력 자리가 없으면 꺼서 보낼 수 없는 요청을 막는다 */
  canReject?: boolean;
  onApprove: (id: string) => void;
  /** 제안 기각 */
  onReject: (id: string) => void;
}

/** 판정이 끝난 블록의 헤더 표시. 승인·반려가 같은 자리에서 같은 시각을 쓴다 */
const VERDICT_BADGES = {
  approved: { Icon: IconCheckCircle, label: '승인됨' },
  rejected: { Icon: IconDelete2, label: '반려됨' },
} as const;

/** 시안은 비활성 버튼이지만 누를 수 없는 표시라 span으로 낸다 */
function VerdictBadge({ Icon, label }: { Icon: ComponentType<SVGProps<SVGSVGElement>>; label: string }) {
  return (
    <span className="bg-fill-normal-interaction-inactive border-line-normal-normal text-body-xsmall text-text-normal-assistive flex h-7.5 shrink-0 items-center gap-1 rounded-lg border px-2">
      <Icon aria-hidden className="text-icon-normal-assistive size-5" />
      {label}
    </span>
  );
}

/** 카드 하단 설명 패널. 수정 이유와 반려 사유가 같은 시각을 쓴다 */
function CardNotePanel({ label, body }: { label: string; body: string }) {
  return (
    <div className="bg-fill-normal-strong flex flex-col gap-2 rounded-xl px-4 py-3">
      <span className="text-body-xsmall text-text-normal-alternative">{label}</span>
      <p className="text-body-small text-text-normal-neutral">{body}</p>
    </div>
  );
}

/**
 * 블록 변경 1건 = 카드 1장. 본문 배치는 kind가 정한다 — modified는 좌우 비교, added·removed는 단일 패널.
 * 개별 블록 수정(연필) 버튼은 시안에 있으나 기능이 범위 밖이라 구현하지 않는다.
 */
export default function BlockDiffCard({
  entry,
  defaultCollapsed = false,
  canReview = true,
  canReject = true,
  onApprove,
  onReject,
}: BlockDiffCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  // 판정이 들어오면 접힘 기본값이 바뀐다 — 카드가 남아 있는 채로 상태만 따라가야 한다
  const [appliedDefault, setAppliedDefault] = useState(defaultCollapsed);
  if (appliedDefault !== defaultCollapsed) {
    setAppliedDefault(defaultCollapsed);
    setCollapsed(defaultCollapsed);
  }

  const { id, kind, title, before, after, reason, rejected = false, approved = false, rejectionReason } = entry;
  const ChevronIcon = collapsed ? IconArrowDropdownRight : IconArrowDropdownDown;
  // 판정이 끝나면 액션 자리를 배지가 대신한다 — 반려·승인 둘 다 흔적을 남긴다
  const verdictBadge = (rejected && VERDICT_BADGES.rejected) || (approved && VERDICT_BADGES.approved) || null;

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

        {verdictBadge ? (
          <VerdictBadge Icon={verdictBadge.Icon} label={verdictBadge.label} />
        ) : (
          canReview && (
            <>
              {/* outline은 테두리 1px이 더해져 solid와 높이가 어긋난다 — 양쪽에 같은 높이를 준다 */}
              {canReject && (
                <Button variant="box-outline-gray" size="sm" className="h-7.5" onClick={() => onReject(id)}>
                  반려
                </Button>
              )}
              <Button variant="box-solid-primary" size="sm" className="h-7.5" onClick={() => onApprove(id)}>
                승인
              </Button>
            </>
          )
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
          {reason && <CardNotePanel label="수정된 이유" body={reason} />}
          {/* 반려 사유는 검토자가 남긴 글이라 판정이 끝난 뒤에도 읽을 자리가 있어야 한다 */}
          {rejected && rejectionReason && <CardNotePanel label="반려 사유" body={rejectionReason} />}
        </>
      )}
    </section>
  );
}
