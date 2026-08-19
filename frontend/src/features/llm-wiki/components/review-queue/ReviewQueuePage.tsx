'use client';

import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowUp from '@/public/icons/icon/arrow_up.svg';
import IconCalendarClock from '@/public/icons/icon/calendar_clock.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconPersonFilled from '@/public/icons/icon/person_filled.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import IconWikiChannelFilled from '@/public/icons/icon/wiki_channel_filled.svg';
import { Button } from '@/shared/components/ui/button';

import type { ReviewQueueRowData } from '../../api/knowledgeReviewMappers';
import type { BlockDiffEntry } from '../../types/llmWikiDiff';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import WikiPageHeader from '../header/WikiPageHeader';
import ChangeSummaryCard from './ChangeSummaryCard';
import BlockDiffSection from './diff/BlockDiffSection';
import DocumentLocationCard from './DocumentLocationCard';
import ReviewParticipantsCard, { type ReviewParticipant } from './ReviewParticipantsCard';
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

export interface ReviewQueuePageProps {
  items: readonly ReviewQueueRowData[];
  /** 목록 전체 건수. 쪽을 나눠 받으므로 items.length와 다를 수 있다 */
  totalCount: number;
  selectedId: string | null;
  onSelectItem: (proposalId: string) => void;

  /** 상세 헤더의 경로. 마지막 마디가 현재 문서다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  /** 우측 "문서 위치" 카드의 경로 — 문서 마디를 뺀 채널 > 폴더다 */
  locationBreadcrumbs: readonly DocumentBreadcrumb[];
  title: string;
  waitingLabel: string;
  /** [BE] 변경안 요약. 큐 목록 응답의 summary다 */
  summary: string;
  participants: readonly ReviewParticipant[];

  entries: readonly BlockDiffEntry[];
  /** [BE] can_review. 판정·발행 진입점 노출을 정한다 */
  canReview: boolean;
  /** 반려 진입점. 사유 입력 자리가 없으면 꺼진다 */
  canReject?: boolean;
  /** 미판정 블록이 남았는지. 남으면 발행 버튼이 잠긴다 */
  publishDisabled: boolean;

  channelOptions: readonly ReviewQueueFilterOption[];
  assigneeOptions: readonly ReviewQueueFilterOption[];
  filters: ReviewQueueFilterState;
  onFiltersChange: (next: ReviewQueueFilterState) => void;

  onPreview: () => void;
  onApproveBlock: (entry: BlockDiffEntry) => void;
  /** canReject가 꺼져 있으면 호출되지 않는다 */
  onRejectBlock?: (entry: BlockDiffEntry) => void;
  onPublish: () => void;
}

/**
 * 검토 큐 화면 — 좌측 목록 · 중앙 제안 상세 · 우측 문서 위치·담당자.
 * 데이터와 동작은 전부 props다. 로딩·에러 시각은 시안이 없어 두지 않는다.
 */
export default function ReviewQueuePage({
  items,
  totalCount,
  selectedId,
  onSelectItem,
  breadcrumbs,
  locationBreadcrumbs,
  title,
  waitingLabel,
  summary,
  participants,
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
}: ReviewQueuePageProps) {
  const selectedIndex = items.findIndex((item) => item.id === selectedId);

  const moveSelection = (offset: number) => {
    const next = items[selectedIndex + offset];
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
          {items.map((item) => (
            <ReviewQueueRow key={item.id} item={item} selected={item.id === selectedId} onSelect={onSelectItem} />
          ))}
        </div>
      </aside>

      {/* 중앙 — 제안 상세 */}
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
                disabled={selectedIndex < 0 || selectedIndex >= items.length - 1}
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
            </>
          }
        />

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex flex-col gap-9 px-9 py-9">
            <div className="flex flex-col gap-3">
              <h2 className="text-heading-xlarge text-text-normal-strong">{title}</h2>
              {/* 작성자 줄은 없다 — LLM 제안이라 큐 응답에 작성자가 실리지 않는다 */}
              <span className="text-body-xsmall text-text-normal-alternative">{waitingLabel}</span>
            </div>

            <ChangeSummaryCard changeCount={entries.length} body={summary} />

            <BlockDiffSection
              entries={entries}
              onPreview={onPreview}
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
            />
          </div>
        </div>

        <ReviewPublishBar canReview={canReview} disabled={publishDisabled} onPublish={onPublish} />
      </div>

      {/* 우측 — 문서 위치·담당자 */}
      <aside className="border-line-normal-neutral flex w-87.5 shrink-0 flex-col overflow-y-auto border-l">
        <DocumentLocationCard breadcrumbs={locationBreadcrumbs} />
        <ReviewParticipantsCard
          participants={participants}
          stackAvatars={participants.map((participant) => ({ src: participant.avatarSrc ?? null }))}
        />
      </aside>
    </div>
  );
}
