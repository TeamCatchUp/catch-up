'use client';

import { useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import DocumentStatusBadge from '@/features/llm-wiki/components/document/DocumentStatusBadge';
import WikiPageHeader from '@/features/llm-wiki/components/header/WikiPageHeader';
import ChangeSummaryCard from '@/features/llm-wiki/components/review-queue/ChangeSummaryCard';
import BlockDiffSection from '@/features/llm-wiki/components/review-queue/diff/BlockDiffSection';
import DocumentLocationCard from '@/features/llm-wiki/components/review-queue/DocumentLocationCard';
import ReviewParticipantsCard, {
  type ReviewParticipant,
} from '@/features/llm-wiki/components/review-queue/ReviewParticipantsCard';
import ReviewPublishBar from '@/features/llm-wiki/components/review-queue/ReviewPublishBar';
import ReviewQueueFilterDropdown, {
  type ReviewQueueFilterSection,
} from '@/features/llm-wiki/components/review-queue/ReviewQueueFilterDropdown';
import ReviewQueueListHeader from '@/features/llm-wiki/components/review-queue/ReviewQueueListHeader';
import ReviewQueueRow from '@/features/llm-wiki/components/review-queue/ReviewQueueRow';
import {
  BASE_WIKI_BLOCKS,
  JUDGED_PROPOSED_BLOCKS,
  LONG_BASE_WIKI_BLOCKS,
  LONG_PROPOSED_WIKI_BLOCKS,
  PROPOSED_WIKI_BLOCKS,
} from '@/features/llm-wiki/fixtures/llmWikiDiffFixtures';
import { WIKI_DOCUMENT_FIXTURES } from '@/features/llm-wiki/fixtures/llmWikiDocumentFixtures';
import {
  REVIEW_QUEUE_ASSIGNEE_OPTIONS,
  REVIEW_QUEUE_CHANNEL_OPTIONS,
  REVIEW_QUEUE_ITEM_FIXTURES,
} from '@/features/llm-wiki/fixtures/llmWikiFixtures';
import type { WikiBlock } from '@/features/llm-wiki/types/llmWikiDiff';
import type { DocumentBreadcrumb } from '@/features/llm-wiki/types/llmWikiModel';
import { computeBlockDiff } from '@/features/llm-wiki/utils/diff/computeBlockDiff';
import IconArrowDown from '@/public/icons/icon/arrow_down.svg';
import IconArrowUp from '@/public/icons/icon/arrow_up.svg';
import IconCalendarClock from '@/public/icons/icon/calendar_clock.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconPersonFilled from '@/public/icons/icon/person_filled.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import IconWikiChannelFilled from '@/public/icons/icon/wiki_channel_filled.svg';
import { Avatar } from '@/shared/components/ui/avatar';
import { Button } from '@/shared/components/ui/button';

/** 검토 대상 문서 mock — 미리보기 라우팅과 breadcrumb·문서 위치의 원천이다 */
const REVIEW_TARGET_DOCUMENT = WIKI_DOCUMENT_FIXTURES[0];

interface ProposalDetailMock {
  baseBlocks: readonly WikiBlock[];
  proposedBlocks: readonly WikiBlock[];
}

/** 제안별 base/proposed 쌍 mock. base revision blocks API가 없어 fixture 쌍이 diff의 유일한 원천이다 */
const PROPOSAL_BLOCKS_MOCK: Record<string, ProposalDetailMock> = {
  'proposal-payment-retry-v3': { baseBlocks: BASE_WIKI_BLOCKS, proposedBlocks: PROPOSED_WIKI_BLOCKS },
  'proposal-merge-refund': { baseBlocks: LONG_BASE_WIKI_BLOCKS, proposedBlocks: LONG_PROPOSED_WIKI_BLOCKS },
  'proposal-rejected-example': { baseBlocks: [BASE_WIKI_BLOCKS[0]], proposedBlocks: JUDGED_PROPOSED_BLOCKS },
};

/** 상세 데이터 단일 진입점. 실 API 도착 시 이 함수만 제안 상세 GET으로 교체된다(복귀 재조회 전제) */
function loadProposalDetail(proposalId: string): ProposalDetailMock {
  return PROPOSAL_BLOCKS_MOCK[proposalId] ?? { baseBlocks: BASE_WIKI_BLOCKS, proposedBlocks: PROPOSED_WIKI_BLOCKS };
}

/** 대기 기간 축 단일 선택 옵션 */
const WAITING_OPTIONS = [
  { id: 'all', label: '전체' },
  { id: 'today', label: '오늘' },
  { id: 'within-7d', label: '7일 이내' },
  { id: 'before', label: '이전' },
] as const;

/** 요약 카드 본문 mock. 영향 문서 건수는 백엔드 대응 값이 없어 표시 문자열째 mock이다 */
const CHANGE_SUMMARY_MOCK = {
  body: '재시도 한도가 1회에서 3회로 늘고, PG 점검 시간 예외 블록이 새로 추가되었습니다. 상담원 수동 재시도 안내 절차는 폐지 제안되었습니다.',
  affectedDocumentsLabel: '영향 문서 2건',
};

/** 담당자 카드 mock — 담당자 API·fixture가 없어 페이지 로컬 데이터다 */
const PARTICIPANTS_MOCK: readonly ReviewParticipant[] = [
  { id: 'participant-author', name: '직원10', description: '1일 전 수정', editing: false, role: '작성자' },
];
const PARTICIPANT_STACK_MOCK = Array.from({ length: 6 }, () => ({ src: null }));

export default function Page() {
  const router = useRouter();

  const [selectedId, setSelectedId] = useState(REVIEW_QUEUE_ITEM_FIXTURES[0].id);
  const [verdicts, setVerdicts] = useState<Record<string, 'approved' | 'rejected'>>({});
  const [channelIds, setChannelIds] = useState<readonly string[]>([]);
  const [assigneeIds, setAssigneeIds] = useState<readonly string[]>([]);
  const [waitingId, setWaitingId] = useState<string>('all');

  // 전송 없는 mock — 실 API의 요청 바디 형태만 기록해 계약 모양을 보존한다
  const verdictRequestRef = useRef<Record<string, unknown> | null>(null);
  const publishRequestRef = useRef<Record<string, unknown> | null>(null);

  const selectedIndex = REVIEW_QUEUE_ITEM_FIXTURES.findIndex((item) => item.id === selectedId);
  const selected = REVIEW_QUEUE_ITEM_FIXTURES[selectedIndex];

  const detail = useMemo(() => loadProposalDetail(selectedId), [selectedId]);
  const entries = useMemo(() => computeBlockDiff(detail.baseBlocks, detail.proposedBlocks), [detail]);
  const displayedEntries = useMemo(
    () => entries.map((entry) => (verdicts[entry.id] === 'rejected' ? { ...entry, rejected: true } : entry)),
    [entries, verdicts],
  );

  const breadcrumbs: DocumentBreadcrumb[] = [
    ...REVIEW_TARGET_DOCUMENT.breadcrumbs.slice(0, -1),
    { kind: 'document', label: selected.title },
  ];

  const selectProposal = (id: string) => {
    setSelectedId(id);
    setVerdicts({});
  };

  const moveSelection = (offset: number) => {
    const next = REVIEW_QUEUE_ITEM_FIXTURES[selectedIndex + offset];
    if (next) selectProposal(next.id);
  };

  const submitBlockVerdict = (entryId: string, verdict: 'approved' | 'rejected') => {
    const entry = entries.find((item) => item.id === entryId);
    // 판정 경로 없는 카드(tombstone 없이 빠진 블록)는 요청 자체가 성립하지 않는다
    if (!entry || entry.blockContentHash === null) return;
    // blockIndex는 저장값이 아니라 현재 배열 자리에서 재계산한다 — 재정렬 후 오판정 방지 계약
    const blockIndex = detail.proposedBlocks.findIndex((block) => block.blockContentHash === entry.blockContentHash);
    verdictRequestRef.current = {
      proposalId: selectedId,
      blockIndex,
      blockContentHash: entry.blockContentHash,
      verdict,
    };
    setVerdicts((prev) => ({ ...prev, [entryId]: verdict }));
  };

  // 미리보기 대상은 제안본이라 proposalId를 동봉한다 — 열람 전용 제안 뷰는 아직 없어 에디터 라우트가 대신한다
  const handlePreview = () => {
    router.push(`/llm-wiki/${REVIEW_TARGET_DOCUMENT.id}?proposalId=${REVIEW_TARGET_DOCUMENT.proposalId}`);
  };

  const handlePublish = () => {
    publishRequestRef.current = { proposalId: selectedId, baseRevisionId: selected.baseRevisionId };
  };

  const filterSections: readonly ReviewQueueFilterSection[] = [
    {
      id: 'target-channel',
      label: '대상 채널',
      Icon: IconWikiChannel,
      searchPlaceholder: '부서명 검색',
      OptionIcon: IconWikiChannelFilled,
      options: REVIEW_QUEUE_CHANNEL_OPTIONS,
      selectedOptionIds: channelIds,
    },
    {
      id: 'assignee',
      label: '담당자',
      Icon: IconPerson,
      searchPlaceholder: '담당자 검색',
      OptionIcon: IconPersonFilled,
      options: REVIEW_QUEUE_ASSIGNEE_OPTIONS,
      selectedOptionIds: assigneeIds,
    },
    {
      id: 'waiting',
      label: '대기 기간',
      Icon: IconCalendarClock,
      options: WAITING_OPTIONS,
      selectedOptionId: waitingId,
      valueLabel: WAITING_OPTIONS.find((option) => option.id === waitingId)?.label,
    },
  ];

  const toggleMultiFilter = (sectionId: string, optionId: string) => {
    const toggle = (ids: readonly string[]) =>
      ids.includes(optionId) ? ids.filter((id) => id !== optionId) : [...ids, optionId];
    if (sectionId === 'target-channel') setChannelIds(toggle);
    if (sectionId === 'assignee') setAssigneeIds(toggle);
  };

  const filtered = channelIds.length > 0 || assigneeIds.length > 0 || waitingId !== 'all';

  return (
    <div className="flex h-full">
      {/* 좌측 — 요청된 변경사항 목록 */}
      <aside className="border-line-normal-neutral flex w-75 shrink-0 flex-col border-r">
        <ReviewQueueListHeader
          count={REVIEW_QUEUE_ITEM_FIXTURES.length}
          filter={
            <ReviewQueueFilterDropdown
              sections={filterSections}
              onSelect={(sectionId, optionId) => {
                if (sectionId === 'waiting') setWaitingId(optionId);
              }}
              onToggle={toggleMultiFilter}
              filtered={filtered}
            />
          }
        />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {REVIEW_QUEUE_ITEM_FIXTURES.map((item) => (
            <ReviewQueueRow key={item.id} item={item} selected={item.id === selectedId} onSelect={selectProposal} />
          ))}
        </div>
      </aside>

      {/* 중앙 — 제안 상세 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <WikiPageHeader
          variant="detail"
          breadcrumbs={breadcrumbs}
          badge={<DocumentStatusBadge status="pending_review" size="sm" />}
          actions={
            <>
              <Button
                variant="icon-only-gray"
                size="md"
                aria-label="다음 변경사항"
                disabled={selectedIndex >= REVIEW_QUEUE_ITEM_FIXTURES.length - 1}
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
              <h2 className="text-heading-xlarge text-text-normal-strong">{selected.title}</h2>
              <div className="text-body-xsmall flex items-center gap-3">
                <Avatar size="small" src={selected.authorProfileImageUrl} />
                <span className="text-text-normal-alternative">작성자</span>
                <span className="text-text-normal-neutral">{selected.authorName}</span>
                <span className="text-text-normal-alternative">{selected.waitingLabel}</span>
              </div>
            </div>

            <ChangeSummaryCard
              changeCount={displayedEntries.length}
              affectedDocumentsLabel={CHANGE_SUMMARY_MOCK.affectedDocumentsLabel}
              body={CHANGE_SUMMARY_MOCK.body}
            />

            <BlockDiffSection
              entries={displayedEntries}
              onPreview={handlePreview}
              onApprove={(id) => submitBlockVerdict(id, 'approved')}
              onReject={(id) => submitBlockVerdict(id, 'rejected')}
            />
          </div>
        </div>

        <ReviewPublishBar onPublish={handlePublish} />
      </div>

      {/* 우측 — 문서 위치·담당자 */}
      <aside className="border-line-normal-neutral flex w-87.5 shrink-0 flex-col overflow-y-auto border-l">
        <DocumentLocationCard breadcrumbs={REVIEW_TARGET_DOCUMENT.breadcrumbs} />
        <ReviewParticipantsCard participants={PARTICIPANTS_MOCK} stackAvatars={PARTICIPANT_STACK_MOCK} />
      </aside>
    </div>
  );
}
