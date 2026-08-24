'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowUp from '@/public/icons/icon/arrow_up.svg';
import IconCalendarClock from '@/public/icons/icon/calendar_clock.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new_24.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconPersonFilled from '@/public/icons/icon/person_filled.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import IconWikiChannelFilled from '@/public/icons/icon/wiki_channel_filled.svg';
import { Button } from '@/shared/components/ui/button';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { MotionState, stepReplace, stepReplaceReduced } from '@/shared/motion';

import type { ReviewQueueRowData } from '../../api/knowledgeReviewMappers';
import type { BlockDiffEntry } from '../../types/llmWikiDiff';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import WikiPageHeader from '../header/WikiPageHeader';
import ChangeSummaryCard from './ChangeSummaryCard';
import BlockDiffSection from './diff/BlockDiffSection';
import DocumentLocationCard from './DocumentLocationCard';
import RejectReasonDialog from './RejectReasonDialog';
import ReviewParticipantsCard, { type OwnerNotice, type ReviewParticipant } from './ReviewParticipantsCard';
import ReviewPublishBar from './ReviewPublishBar';
import ReviewQueueFilterDropdown, {
  type ReviewQueueFilterOption,
  type ReviewQueueFilterSection,
} from './ReviewQueueFilterDropdown';
import {
  isReviewQueueFiltered,
  REVIEW_QUEUE_WAITING_OPTIONS,
  type ReviewQueueFilterState,
  type ReviewQueueWaitingId,
} from './reviewQueueFilters';
import ReviewQueueListHeader from './ReviewQueueListHeader';
import ReviewQueueRow from './ReviewQueueRow';
import ReviewQueueDetailSkeleton from './states/ReviewQueueDetailSkeleton';
import ReviewQueueEmptyState from './states/ReviewQueueEmptyState';
import ReviewQueueListSkeleton from './states/ReviewQueueListSkeleton';

export interface ReviewQueuePageProps {
  items: readonly ReviewQueueRowData[];
  /** 목록 전체 건수. 쪽을 나눠 받으므로 items.length와 다를 수 있다 */
  totalCount: number;
  /** 목록 첫 조회 전인지. 서면 좌측 목록과 상세가 함께 골격이 된다 */
  listPending?: boolean;
  /** 고른 안건의 상세를 기다리는 중인지 */
  detailPending?: boolean;
  selectedId: string | null;
  onSelectItem: (proposalId: string) => void;

  /** 상세 헤더의 경로. 마지막 마디가 현재 문서다 — 문서 위치 카드도 같은 경로를 그린다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  title: string;
  waitingLabel: string;
  /** [BE] 변경안 요약. 큐 목록 응답의 summary다 */
  summary: string;
  participants: readonly ReviewParticipant[];
  /** 담당자 카드의 안내 배너 분기. null이면 배너 없음(내가 담당자) */
  ownerNotice?: OwnerNotice | null;
  /** 담당자 지정 권한 — 채널 관리자 또는 담당자 본인(백엔드 can_manage_owners) */
  canAssignOwners?: boolean;
  /** 담당자 해제 권한 — 관리자만 */
  canRemoveOwners?: boolean;
  /** 담당자 추가 후보. id는 user_id 문자열이다 */
  ownerCandidates?: readonly ReviewQueueFilterOption[];
  onAssignOwners?: (userIds: readonly number[]) => void;
  onRemoveOwner?: (userId: number) => void;

  entries: readonly BlockDiffEntry[];
  /** [BE] can_review. 판정·발행 진입점 노출을 정한다 */
  canReview: boolean;
  /** 카드별 반려 진입점. 사유 입력 자리가 없으면 꺼진다 */
  canReject?: boolean;
  /** 미판정 블록이 남았는지. 남으면 발행 버튼이 잠긴다 */
  publishDisabled: boolean;

  channelOptions: readonly ReviewQueueFilterOption[];
  assigneeOptions: readonly ReviewQueueFilterOption[];
  filters: ReviewQueueFilterState;
  onFiltersChange: (next: ReviewQueueFilterState) => void;

  onPreview: () => void;
  onApproveBlock: (entry: BlockDiffEntry) => void;
  /** 카드 반려 클릭. 요청은 사유 입력을 거쳐 나간다 */
  onRejectBlock?: (entry: BlockDiffEntry) => void;
  onPublish: () => void;

  /** 미판정 카드 일괄 승인. 발행은 별도 액션으로 남는다 */
  onApproveAll: () => void;
  /** 사유 입력 다이얼로그의 열림 상태. 요청 성패를 아는 소비처가 든다 */
  rejectDialogOpen: boolean;
  onRejectDialogOpenChange: (open: boolean) => void;
  /** 변경안 통째 반려. 사유는 이미 트림돼 있다 */
  onRejectAll: (reason: string) => void;
  rejectPending?: boolean;

  /** 블록 반려 사유 입력의 열림 상태. 어느 블록인지는 소비처가 든다 */
  blockRejectDialogOpen?: boolean;
  onBlockRejectDialogOpenChange?: (open: boolean) => void;
  /** 블록 반려 확정. 사유는 이미 트림돼 있다 */
  onRejectBlockSubmit?: (reason: string) => void;
  blockRejectPending?: boolean;
}

/** 블록 반려 사유 입력의 문구. 전체 반려 다이얼로그를 그대로 쓰고 문구만 갈아 끼운다 */
const BLOCK_REJECT_COPY = {
  title: '블록 반려',
  description: '반려 사유는 작성자에게 그대로 전달됩니다.',
  submitLabel: '반려',
} as const;

/**
 * 검토 큐 화면 — 좌측 목록 · 헤더 아래로 중앙 제안 상세와 우측 문서 위치·담당자.
 * 데이터와 동작은 전부 props다. 로딩·에러 시각은 시안이 없어 두지 않는다.
 */
export default function ReviewQueuePage({
  items,
  totalCount,
  listPending = false,
  detailPending = false,
  selectedId,
  onSelectItem,
  breadcrumbs,
  title,
  waitingLabel,
  summary,
  participants,
  ownerNotice = null,
  canAssignOwners = false,
  canRemoveOwners = false,
  ownerCandidates = [],
  onAssignOwners,
  onRemoveOwner,
  entries,
  canReview,
  canReject = true,
  publishDisabled,
  channelOptions,
  assigneeOptions,
  filters,
  onFiltersChange,
  onPreview,
  onApproveBlock,
  onRejectBlock,
  onPublish,
  onApproveAll,
  rejectDialogOpen,
  onRejectDialogOpenChange,
  onRejectAll,
  rejectPending = false,
  blockRejectDialogOpen = false,
  onBlockRejectDialogOpenChange,
  onRejectBlockSubmit,
  blockRejectPending = false,
}: ReviewQueuePageProps) {
  const selectedIndex = items.findIndex((item) => item.id === selectedId);
  // 목록이 비면 그릴 상세가 없다 — 첫 조회를 기다리는 동안에는 골격이 서고 안내는 서지 않는다
  const isEmpty = items.length === 0 && !listPending;
  // 목록을 아직 기다리는 동안에도 상세 자리는 골격으로 채운다
  const showDetailSkeleton = listPending || detailPending;
  // 고른 안건이 목록에서 빠진 순간에도 남은 안건이 있으면 다음으로 갈 수 있어야 한다
  const canMoveNext = selectedIndex < 0 ? items.length > 0 : selectedIndex < items.length - 1;

  const prefersReducedMotion = usePrefersReducedMotion();
  // 상세가 넘어가는 방향. 목록에서 아래 안건을 고르면 아래에서, 위면 위에서 들어온다
  const [swap, setSwap] = useState({ id: selectedId, direction: 1 });
  if (swap.id !== selectedId) {
    // 자리는 지금 목록에서 다시 읽는다 — 줄이 빠진 뒤의 낡은 자리로 재면 방향이 뒤집힌다
    const previousIndex = items.findIndex((item) => item.id === swap.id);
    setSwap({ id: selectedId, direction: selectedIndex < previousIndex ? -1 : 1 });
  }

  const moveSelection = (offset: number) => {
    const next = selectedIndex < 0 ? items[0] : items[selectedIndex + offset];
    if (next) onSelectItem(next.id);
  };

  const filterSections: readonly ReviewQueueFilterSection[] = [
    {
      id: 'target-channel',
      label: '대상 채널',
      Icon: IconWikiChannel,
      searchPlaceholder: '부서명 검색',
      OptionIcon: IconWikiChannelFilled,
      options: channelOptions,
      selectedOptionIds: filters.channelIds,
    },
    {
      id: 'assignee',
      label: '담당자',
      Icon: IconPerson,
      searchPlaceholder: '담당자 검색',
      OptionIcon: IconPersonFilled,
      options: assigneeOptions,
      selectedOptionIds: filters.assigneeIds,
    },
    {
      id: 'waiting',
      label: '대기 기간',
      Icon: IconCalendarClock,
      options: REVIEW_QUEUE_WAITING_OPTIONS,
      selectedOptionId: filters.waitingId,
      valueLabel: REVIEW_QUEUE_WAITING_OPTIONS.find((option) => option.id === filters.waitingId)?.label,
    },
  ];

  const toggleMultiFilter = (sectionId: string, optionId: string) => {
    const toggle = (ids: readonly string[]) =>
      ids.includes(optionId) ? ids.filter((id) => id !== optionId) : [...ids, optionId];

    if (sectionId === 'target-channel') onFiltersChange({ ...filters, channelIds: toggle(filters.channelIds) });
    if (sectionId === 'assignee') onFiltersChange({ ...filters, assigneeIds: toggle(filters.assigneeIds) });
  };

  return (
    <div className="flex h-full">
      {/* 좌측 — 요청된 변경사항 목록 */}
      <aside className="border-line-normal-neutral flex w-75 shrink-0 flex-col border-r">
        <ReviewQueueListHeader
          count={totalCount}
          filter={
            <ReviewQueueFilterDropdown
              sections={filterSections}
              onSelect={(sectionId, optionId) => {
                if (sectionId === 'waiting') {
                  onFiltersChange({ ...filters, waitingId: optionId as ReviewQueueWaitingId });
                }
              }}
              onToggle={toggleMultiFilter}
              filtered={isReviewQueueFiltered(filters)}
            />
          }
        />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {listPending ? (
            <ReviewQueueListSkeleton />
          ) : (
            items.map((item) => (
              <ReviewQueueRow key={item.id} item={item} selected={item.id === selectedId} onSelect={onSelectItem} />
            ))
          )}
        </div>
      </aside>

      {isEmpty ? (
        <ReviewQueueEmptyState />
      ) : (
        // 헤더는 중앙과 우측 패널을 함께 덮는다 — 좌측 목록만 자기 열을 지킨다
        <div className="flex min-w-0 flex-1 flex-col">
          <WikiPageHeader
            variant="detail"
            breadcrumbs={breadcrumbs}
            actions={
              <>
                <Button
                  variant="icon-only-gray"
                  size="md"
                  aria-label="다음 변경사항"
                  disabled={!canMoveNext}
                  onClick={() => moveSelection(1)}
                >
                  <IconArrowDown aria-hidden className="size-6" />
                </Button>
                <Button
                  variant="icon-only-gray"
                  size="md"
                  aria-label="이전 변경사항"
                  disabled={selectedIndex <= 0}
                  onClick={() => moveSelection(-1)}
                >
                  <IconArrowUp aria-hidden className="size-6" />
                </Button>
                <Button variant="box-outline-gray" size="md" onClick={onPreview}>
                  미리보기
                  <IconOpenInNew aria-hidden className="size-5" />
                </Button>
              </>
            }
          />

          <div className="flex min-h-0 flex-1">
            {/* 중앙 — 제안 상세 */}
            <div className="flex min-w-0 flex-1 flex-col">
              {/* 스크롤 상자는 그대로 두고 안쪽만 교체한다 — 상자가 움직이면 스크롤바가 함께 튄다 */}
              <div className="min-h-0 flex-1 overflow-y-auto">
                <AnimatePresence mode="wait" custom={swap.direction} initial={false}>
                  <motion.div
                    key={showDetailSkeleton ? 'loading' : (selectedId ?? 'none')}
                    custom={swap.direction}
                    variants={prefersReducedMotion ? stepReplaceReduced : stepReplace}
                    initial={MotionState.Hidden}
                    animate={MotionState.Visible}
                    exit={MotionState.Exit}
                    className="flex flex-col gap-9 px-9 py-9"
                  >
                    {showDetailSkeleton ? (
                      <ReviewQueueDetailSkeleton />
                    ) : (
                      <>
                        <div className="flex flex-col gap-3">
                          <h2 className="text-heading-xlarge text-text-normal-strong">{title}</h2>
                          {/* 작성자 줄은 없다 — LLM 제안이라 큐 응답에 작성자가 실리지 않는다 */}
                          <span className="text-body-xsmall text-text-normal-alternative">{waitingLabel}</span>
                        </div>

                        <ChangeSummaryCard changeCount={entries.length} body={summary} />

                        <BlockDiffSection
                          entries={entries}
                          canReview={canReview}
                          canReject={canReject}
                          onApprove={(id) => {
                            const entry = entries.find((item) => item.id === id);
                            if (entry) onApproveBlock(entry);
                          }}
                          onReject={(id) => {
                            const entry = entries.find((item) => item.id === id);
                            if (entry) onRejectBlock?.(entry);
                          }}
                          onApproveAll={onApproveAll}
                          onRejectAll={() => onRejectDialogOpenChange(true)}
                        />
                      </>
                    )}
                  </motion.div>
                </AnimatePresence>
              </div>

              <ReviewPublishBar canReview={canReview} disabled={publishDisabled} onPublish={onPublish} />
            </div>

            {/* 우측 — 문서 위치·담당자 */}
            <aside className="border-line-normal-neutral flex w-87.5 shrink-0 flex-col overflow-y-auto border-l">
              <DocumentLocationCard breadcrumbs={breadcrumbs} />
              <ReviewParticipantsCard
                participants={participants}
                notice={ownerNotice}
                canAssign={canAssignOwners}
                canRemove={canRemoveOwners}
                candidates={ownerCandidates}
                onAssign={onAssignOwners}
                onRemove={onRemoveOwner}
              />
            </aside>
          </div>

          <RejectReasonDialog
            open={rejectDialogOpen}
            onOpenChange={onRejectDialogOpenChange}
            submitting={rejectPending}
            onSubmit={onRejectAll}
          />

          <RejectReasonDialog
            open={blockRejectDialogOpen}
            onOpenChange={(open) => onBlockRejectDialogOpenChange?.(open)}
            title={BLOCK_REJECT_COPY.title}
            description={BLOCK_REJECT_COPY.description}
            submitLabel={BLOCK_REJECT_COPY.submitLabel}
            submitting={blockRejectPending}
            onSubmit={(reason) => onRejectBlockSubmit?.(reason)}
          />
        </div>
      )}
    </div>
  );
}
