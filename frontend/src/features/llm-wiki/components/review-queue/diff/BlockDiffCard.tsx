'use client';

import { type ComponentType, type SVGProps, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import IconArrowDropdownDown from '@/public/icons/icon/arrow_dropdown_down.svg';
import IconArrowDropdownRight from '@/public/icons/icon/arrow_dropdown_right.svg';
import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import IconDelete2 from '@/public/icons/icon/delete_2.svg';
import IconReviewAgain from '@/public/icons/icon/icon_left.svg';
import { Button } from '@/shared/components/ui/button';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { disclosureExpand, disclosureExpandReduced, MotionState } from '@/shared/motion';
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
  onReset?: (id: string) => void;
  resetPending?: boolean;
}

/** 판정이 끝난 블록의 헤더 표시. 승인·반려가 같은 자리에서 같은 시각을 쓴다 */
const VERDICT_BADGES = {
  approved: {
    Icon: IconCheckCircle,
    label: '승인됨',
    className: 'bg-accent-light-blue-lighten text-accent-light-blue-default',
  },
  rejected: {
    Icon: IconDelete2,
    label: '반려됨',
    className: 'bg-fill-normal-interaction-hover text-text-normal-alternative',
  },
} as const;

/** 시안은 비활성 버튼이지만 누를 수 없는 표시라 span으로 낸다 */
function VerdictBadge({
  Icon,
  label,
  className,
}: {
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
  className: string;
}) {
  return (
    <span
      className={cn('text-body-xsmall rounded-md2 flex h-7.5 shrink-0 items-center gap-1 px-1.5 py-0.5', className)}
    >
      <Icon aria-hidden className="size-4.5" />
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
  onReset,
  resetPending = false,
}: BlockDiffCardProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
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
    <section className="border-line-normal-neutral flex flex-col rounded-xl border px-5 py-[15px]">
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
        {verdictBadge ? (
          <>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <h3 className="text-heading-medium text-text-normal-normal max-w-[383px] min-w-0 truncate">{title}</h3>
              <VerdictBadge Icon={verdictBadge.Icon} label={verdictBadge.label} className={verdictBadge.className} />
            </div>
            {canReview && onReset && (
              <Button
                variant="box-outline-gray"
                size="sm"
                className="h-7.5"
                disabled={resetPending}
                onClick={() => onReset(id)}
              >
                <IconReviewAgain aria-hidden className="size-5" />
                다시 검토하기
              </Button>
            )}
          </>
        ) : (
          <>
            <h3 className="text-heading-medium text-text-normal-normal min-w-0 flex-1 truncate">{title}</h3>
            {canReview && (
              <>
                {canReject && (
                  <Button variant="box-outline-gray" size="sm" className="h-7.5" onClick={() => onReject(id)}>
                    반려
                  </Button>
                )}
                <Button variant="box-solid-primary" size="sm" className="h-7.5" onClick={() => onApprove(id)}>
                  승인
                </Button>
              </>
            )}
          </>
        )}
      </header>

      {/* 헤더와의 간격은 안쪽 pt로 든다 — 높이 축소와 함께 사라져야 접힌 뒤 빈 gap이 남지 않는다 */}
      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            key="body"
            variants={prefersReducedMotion ? disclosureExpandReduced : disclosureExpand}
            initial={MotionState.Hidden}
            animate={MotionState.Visible}
            exit={MotionState.Exit}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-4 pt-4">
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
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
