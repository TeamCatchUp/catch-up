import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { BASE_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES, PROPOSED_WIKI_BLOCKS } from '../../fixtures/llmWikiDiffFixtures';
import { REVIEW_QUEUE_CHANNEL_OPTIONS, REVIEW_QUEUE_ITEM_FIXTURES } from '../../fixtures/llmWikiFixtures';
import { buildBlockDiff } from '../../utils/diff/buildBlockDiff';
import { INITIAL_REVIEW_QUEUE_FILTER_STATE } from './reviewQueueFilters';
import ReviewQueuePage from './ReviewQueuePage';

const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
const selected = REVIEW_QUEUE_ITEM_FIXTURES[0];

/** 담당자 옵션 id는 user_id 문자열이다 — 서버 파라미터가 숫자라 문자 id는 담당자로 세지 않는다 */
const ASSIGNEE_OPTIONS = [
  { id: '1', label: '팀원F' },
  { id: '2', label: '직원10' },
];

/** 남이 담당자·내가 관리자인 판 — 판정(can_review)은 닫히고 담당자 관리만 열린다 */
const OTHER_OWNER_ADMIN_ARGS = {
  // 내가 관리자여도 남의 행은 담당자 배지뿐이다 — 서버가 남의 관리자 여부를 주지 않는다
  participants: [{ id: '1', userId: 1, name: '팀원F', roles: ['담당자'] }],
  ownerNotice: 'other-owner',
  canReview: false,
  canAssignOwners: true,
  canRemoveOwners: true,
  ownerCandidates: [
    { id: '2', label: '직원10' },
    { id: '3', label: '이진수' },
    { id: '6', label: '팀원G', suffixLabel: '(나)' },
  ],
} as const;

const meta = {
  title: 'Screens/LLM Wiki/ReviewQueuePage',
  component: ReviewQueuePage,
  tags: ['autodocs'],
  /** 선택 행은 소비처(라우트)가 든다 — 스토리는 그 자리를 로컬 state로 대신한다. */
  render: function ReviewQueueStory(args) {
    const [selectedId, setSelectedId] = useState(args.selectedId);
    const [rejectDialogOpen, setRejectDialogOpen] = useState(args.rejectDialogOpen);
    const [blockRejectOpen, setBlockRejectOpen] = useState(args.blockRejectDialogOpen ?? false);
    // 라우트는 고른 안건의 상세를 다시 받아온다 — 스토리는 픽스처 행에서 같은 값을 꺼낸다
    const selectedRow = args.items.find((item) => item.id === selectedId);

    return (
      <div className="h-225">
        <ReviewQueuePage
          {...args}
          selectedId={selectedId}
          title={selectedRow?.title ?? args.title}
          waitingLabel={selectedRow?.waitingLabel ?? args.waitingLabel}
          onSelectItem={(id) => {
            args.onSelectItem(id);
            setSelectedId(id);
          }}
          rejectDialogOpen={rejectDialogOpen}
          onRejectDialogOpenChange={(open) => {
            args.onRejectDialogOpenChange(open);
            setRejectDialogOpen(open);
          }}
          // 카드 반려는 요청을 곧바로 내지 않고 사유 입력을 연다 — 라우트가 하는 일을 스토리가 대신한다
          onRejectBlock={(entry) => {
            args.onRejectBlock?.(entry);
            setBlockRejectOpen(true);
          }}
          blockRejectDialogOpen={blockRejectOpen}
          onBlockRejectDialogOpenChange={(open) => {
            args.onBlockRejectDialogOpenChange?.(open);
            setBlockRejectOpen(open);
          }}
        />
      </div>
    );
  },
  args: {
    items: REVIEW_QUEUE_ITEM_FIXTURES,
    totalCount: REVIEW_QUEUE_ITEM_FIXTURES.length,
    selectedId: selected.id,
    onSelectItem: fn(),
    breadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '승인·실패 처리' },
      { kind: 'document', label: selected.title },
    ],
    title: selected.title,
    waitingLabel: selected.waitingLabel,
    summary: '재시도 한도가 1회에서 3회로 늘고 PG 점검 시간 예외가 추가되었습니다.',
    // 내가 담당자인 문서가 기본 판 — 판정이 열리고 배너가 없다. 담당자 본인은 지정만 열린다(해제는 관리자만)
    participants: [{ id: '6', userId: 6, name: '팀원G', isMe: true, roles: ['담당자'] }],
    ownerNotice: null,
    canAssignOwners: true,
    canRemoveOwners: false,
    ownerCandidates: [
      { id: '1', label: '팀원F' },
      { id: '2', label: '직원10' },
      { id: '3', label: '이진수' },
    ],
    onAssignOwners: fn(),
    onRemoveOwner: fn(),
    entries,
    canReview: true,
    publishDisabled: false,
    channelOptions: REVIEW_QUEUE_CHANNEL_OPTIONS,
    assigneeOptions: ASSIGNEE_OPTIONS,
    filters: INITIAL_REVIEW_QUEUE_FILTER_STATE,
    onFiltersChange: fn(),
    onPreview: fn(),
    onApproveBlock: fn(),
    onRejectBlock: fn(),
    onPublish: fn(),
    onApproveAll: fn(),
    rejectDialogOpen: false,
    onRejectDialogOpenChange: fn(),
    onRejectAll: fn(),
    blockRejectDialogOpen: false,
    onBlockRejectDialogOpenChange: fn(),
    onRejectBlockSubmit: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17564-127037',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17564:127037',
      },
      viewport: { width: 1400, height: 900 },
      states: [
        'default',
        'detail-swap',
        'undecided-blocks',
        'no-review-permission',
        'other-owner-as-admin',
        'no-owner-as-admin',
        'no-owner-as-member',
        'no-reject-path',
        'reject-reason',
        'block-reject-reason',
        'bulk-approved',
        'owner-management',
        'empty-queue',
        'empty-by-filter',
        'list-first-load',
        'detail-first-load',
      ],
      reuseNotes: [
        'ReviewQueueListHeader·ReviewQueueRow·ReviewQueueFilterDropdown·WikiPageHeader(detail)·ChangeSummaryCard·BlockDiffSection·DocumentLocationCard·ReviewParticipantsCard(OwnerAddPopover·OwnerDetailPopover 동봉)·ReviewPublishBar·RejectReasonDialog를 조립만 한다.',
      ],
      dataNotes: [
        '화면은 데이터를 props로만 받는다 — 큐·상세 조회와 판정·발행 요청은 라우트가 낸다. 스토리는 MSW 없이 fixture를 주입한다.',
        'diff 카드 짝짓기는 서버 block_changes가 정한다. 프론트는 자리만 따라가고 단어 강조만 만든다 — 같은 안건이 소비자마다 다르게 보이지 않기 위해서다.',
        '발행 버튼은 판정 경로가 있는 카드가 모두 판정될 때까지 잠긴다 — 세는 대상이 서버가 준 변경 목록뿐이라, 변경 없는 블록(서버가 결정을 면제하는 자리)은 카드가 없어 잠금에 끼어들지 않는다. 그래도 남는 미판정은 서버가 409로 거절하고 그 메시지가 토스트로 뜬다 — 일괄 처리(undecided)는 사람이 보지 않은 블록을 자동 승인하게 되어 쓰지 않는다.',
        '카드별 반려도 전체 반려와 같은 사유 입력 다이얼로그를 거친다 — 문구만 갈아 끼운다. 빈 사유는 서버가 422로 막는다.',
        '전체 승인·반려는 판정 경로가 있는 전 카드에 블록 판정을 일괄로 보낸다(반려는 전 블록이 사유를 공유한다) — 이미 판정된 카드도 덮어써서 승인·반려가 뒤집힌다. 다시 읽은 상세의 판정으로 카드가 접히고 발행 바가 열린다(BulkApproved). 발행은 별도 클릭이다.',
        '발행에 성공하면 그 안건이 큐에서 빠지고 소비처가 다음 안건을 골라 준다 — 남은 안건이 없으면 빈 안내가 선다. 화면은 받은 selectedId를 그릴 뿐이다.',
        '고른 안건이 목록에서 빠진 순간에도 "다음"은 남은 첫 줄로 간다 — 판정 뒤 검토 흐름이 끊기면 안 된다.',
        '미리보기는 발행본이 아니라 판정 반영 제안본을 새 탭으로 연다 — 발행된 적 없는 문서도 열린다.',
        '전체 승인·반려는 판정이 시작된 뒤에도 잠기지 않는다 — 블록 판정은 PUT이라 같은 자리에 다시 보내면 갱신으로 흡수된다.',
        '채널·담당자 축은 서버가 하나씩만 받는다 — 둘 이상 고르면 파라미터로 나가지 않고 받은 쪽에서 좁힌다. 좁히기는 라우트가 맡고 화면은 관여하지 않는다.',
        '다중 선택 좁히기는 서버가 돌려준 첫 50건 위에서만 이뤄진다 — 그 밖의 일치 안건은 목록·건수에서 조용히 빠질 수 있다(서버가 축당 단일 값만 받는 한계, 서버 협상 대상).',
        '보낼 블록이 없는 전체 반려는 요청 없이 닫고 안내 토스트를 띄운다 — 문구 "반려할 블록이 없습니다"는 시안 없는 자작이다.',
        '담당자 지정 확인 모달 본문은 시안 실측 문구를 사용자 확정 문구로 교체했다 — 권한 이전(담당자만 판정·내보내기)을 정확히 서술하기 위해서다.',
        '빈 큐는 시안이 없다(감사 MISSING·높음). 새 시각을 만들지 않고 대시보드 빈 표와 같은 일러스트·타이포를 쓰며, 필터 결과 0건도 같은 안내다 — 문구를 가르는 근거가 없다. 디자이너 확인 대상.',
        '목록이 비면 좌측 머리글과 필터는 남는다 — 필터로 비운 경우 되돌릴 경로가 사라지면 안 된다.',
        '첫 로딩은 좌측 목록과 상세 자리에 각각 골격을 세운다(사용자 확정) — 시안 MISSING이라 행·카드 기하만 근사한 자작분이다. 목록을 기다리는 동안에는 빈 안내 대신 골격이 서서 "없음"으로 오독되지 않는다.',
        '상세 골격은 안건 교체와 같은 모션 상자(stepReplace) 안에서 상태만 갈아 끼운다 — 로딩이 별도 레이어로 튀지 않는다.',
        '에러 시각은 시안이 없어 만들지 않는다 — 조회 실패는 판정 토스트와 같은 전역 기본 자리에 문구만 띄운다.',
        '담당자 카드(8/24): 배너 분기·+ 버튼·추가 드롭다운·확인 모달·해제 팝오버는 라우트가 권한(can_manage_owners 규칙: 지정=관리자∨담당자 본인, 해제=관리자만)과 데이터를 실어 준다. 후보 직책(B17)·담당자 활동 시각(B18)은 API에 없어 그 구역을 비운다.',
        '판정(can_review)은 담당자 관리와 규칙이 다르다 — 담당자가 있으면 담당자 본인만(관리자도 못 한다), 없으면 구성원 누구나.',
        '역할 배지는 배열이다 — 담당자이면서 채널 관리자면 배지 둘이 나란히 선다. 채널 관리자 배지는 내 행에만 붙는다 — 서버가 내 관리자 여부(is_admin)만 주고 남의 관리자 여부는 주지 않는다.',
        '담당자 0명 + 내가 관리자면 내 행이 채널 관리자 배지만 달고 선다. 배너는 그대로 판정 규칙(구성원 누구나)을 말한다 — 배지는 역할 표시일 뿐 검토자 지정이 아니고, 폴백 행은 해제 팝오버도 갖지 않는다.',
        '담당자 미지정 배너 문구는 시안 실측("채널 관리자가 검토")이 서버 규칙과 어긋나 사용자 확정 문구("구성원 누구나 검토")로 교체했다.',
        '담당자 행 규격은 확정 노드로 닫혔다(기본 18788:55469·호버 18773:89303, 2026-08-24) — 행 패딩 4·radius 8·행 간 2, 호버 채움 rgba(30,33,36,6%) = fill-normal-interaction-hover. 시안은 행 호버 상태만 그리고 팝오버 개폐 방식은 그리지 않아, 해제 동선(클릭 액션)이 끊기지 않게 클릭 트리거를 유지했다. 해제 팝오버는 앵커 좌측(side=left)에 선다(사용자 지시 — 우측 패널이라 아래보다 좌측이 안전).',
        '+ 버튼 툴팁도 확정 노드로 닫혔다(18788:55263, 2026-08-24) — add_small 아이콘 20 + 제목 "담당자 추가하기", 좌측 배치(사용자 지시). 배경 75% 검정·radius 8·패딩 6·label(rg)/xsmall 흰 글자는 공용 Tooltip sm과 일치해 소비만 한다. 그림자만 공용 shadow-tooltip(알파 12%)이 시안 Shadow/tooltip(10%)과 미세하게 어긋난다 — 공용 토큰이라 기록만.',
        '문서 위치 카드는 헤더와 같은 breadcrumbs를 그리고 마지막 문서 마디에 현재 위치 점(6px 파랑)을 찍는다 — NavTree는 점을 표현하지 못해 정적 마크업으로 교체했다.',
      ],
      layoutNotes: [
        '좌 300 · 우 350 고정, 중앙이 남는 폭을 흡수한다. 높이는 셸이 준다 — 스토리가 900 슬롯을 흉내낸다.',
        '헤더는 좌측 목록을 뺀 나머지 폭을 전부 덮는다 — 중앙과 우측 패널이 그 아래에 나란히 선다.',
      ],
      interactionNotes: [
        '안건을 바꾸면 중앙 상세만 stepReplace로 교체된다(AnimatePresence mode="wait"). 스크롤 상자와 좌·우 패널은 제자리다.',
        '방향은 목록 순서에서 읽는다 — 아래 안건은 아래에서 들어오고 위 안건은 위에서 들어온다.',
        'reduced motion에서는 stepReplaceReduced로 갈아타 이동 없이 짧은 fade만 남는다 — 변형 정의 검증은 shared/motion/presets.test.ts에 있다.',
      ],
    }),
  },
} satisfies Meta<typeof ReviewQueuePage>;

export default meta;
type Story = StoryObj<typeof ReviewQueuePage>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 좌측 목록 — 헤더 건수와 행이 함께 선다
    const listHeader = canvas.getByText('요청된 변경사항').closest('div')!;
    await expect(within(listHeader).getByText(String(REVIEW_QUEUE_ITEM_FIXTURES.length))).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 2, name: selected.title })).toBeInTheDocument();
    await expect(canvas.getByText('환불 문서 병합 제안')).toBeInTheDocument();

    // 헤더는 좌측 목록 오른쪽 전체를 덮는다 — 미리보기는 이 헤더의 마지막 액션이다
    const header = canvas.getByRole('navigation', { name: '현재 위치' }).closest('header')!;
    await expect(within(header).getByRole('button', { name: /미리보기/ })).toBeInTheDocument();
    await expect(within(header).getByRole('button', { name: '다음 변경사항' })).toBeInTheDocument();
    await userEvent.click(within(header).getByRole('button', { name: /미리보기/ }));
    await expect(args.onPreview).toHaveBeenCalled();

    // 헤더가 우측 패널 위까지 뻗는지는 눈이 아니라 기하로 본다
    const sidePanel = canvas.getByText('문서 위치').closest('aside')!;
    await expect(header.getBoundingClientRect().right).toBeGreaterThanOrEqual(sidePanel.getBoundingClientRect().right);

    // 우측 담당자 카드 — 내가 담당자라 배너 없이 내 행과 추가 진입점만 선다
    await expect(canvas.getByText('(나)')).toBeInTheDocument();
    await expect(canvas.queryByText('담당자가 검토할 문서입니다')).toBeNull();
    await expect(canvas.queryByText('담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.')).toBeNull();
    await expect(canvas.getByRole('button', { name: '담당자 추가하기' })).toBeInTheDocument();
    // 배지는 담당자 하나다 — 관리자가 아니라 채널 관리자 배지는 서지 않는다
    const participantsCard = canvas.getByRole('heading', { name: '담당자' }).closest('section')!;
    await expect(within(participantsCard).getAllByText('담당자')).toHaveLength(2);
    await expect(within(participantsCard).queryByText('채널 관리자')).toBeNull();

    // 중앙 — 요약과 diff 카드 3장
    await expect(canvas.getByText('변경 내용')).toBeInTheDocument();
    await expect(canvas.getByText('이렇게 바뀌었어요')).toBeInTheDocument();
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('PG 점검 시간 예외')).toBeInTheDocument();
    await expect(canvas.getByText('수동 재시도 안내')).toBeInTheDocument();

    // 승인은 판정 경로 키를 그대로 들고 나간다 — 낙관적 잠금의 재료다
    await userEvent.click(canvas.getAllByRole('button', { name: '승인' })[0]);
    await expect(args.onApproveBlock).toHaveBeenCalledWith(
      expect.objectContaining({ blockIndex: 0, blockContentHash: expect.stringMatching(/^sha256:/) }),
    );

    await userEvent.click(canvas.getByRole('button', { name: '전체 승인' }));
    await expect(args.onApproveAll).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: '최종 내보내기' }));
    await expect(args.onPublish).toHaveBeenCalled();

    // 다른 행을 고르면 선택이 옮겨간다
    await userEvent.click(canvas.getByText('환불 문서 병합 제안'));
    await expect(args.onSelectItem).toHaveBeenCalledWith('proposal-merge-refund');
  },
};

/**
 * 헤더 ↓/↑ 로 다음·이전 안건을 오갈 때 중앙 상세가 통째로 교체된다.
 * 교체 중 두 상세가 겹쳐 서지 않는지를 본다 — 겹치면 스크롤 상자 높이가 두 배로 튄다.
 */
export const DetailSwap: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const header = canvas.getByRole('navigation', { name: '현재 위치' }).closest('header')!;
    const [first, second] = REVIEW_QUEUE_ITEM_FIXTURES;

    const detailTitle = (name: string) => canvas.queryByRole('heading', { level: 2, name });
    await expect(detailTitle(first.title)).toBeInTheDocument();

    await userEvent.click(within(header).getByRole('button', { name: '다음 변경사항' }));
    await waitFor(async () => {
      await expect(detailTitle(second.title)).toBeInTheDocument();
    });
    await expect(detailTitle(first.title)).toBeNull();

    // 위로 되돌리면 앞 안건이 다시 선다 — 방향만 뒤집히고 안무는 같다
    await userEvent.click(within(header).getByRole('button', { name: '이전 변경사항' }));
    await waitFor(async () => {
      await expect(detailTitle(first.title)).toBeInTheDocument();
    });
    await expect(detailTitle(second.title)).toBeNull();
  },
};

/**
 * 발행 버튼이 잠긴 상태. 상세가 아직 없거나 판정하지 않은 카드가 남았을 때다.
 */
export const PublishLocked: Story = {
  args: { publishDisabled: true },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 잠긴 버튼은 pointer-events가 없어 클릭 자체가 닿지 않는다
    await expect(canvas.getByRole('button', { name: '최종 내보내기' })).toBeDisabled();
    await expect(args.onPublish).not.toHaveBeenCalled();
  },
};

/** 남이 담당자 · 일반 구성원 — 판정·발행 진입점이 사라지고 담당자 관리도 닫힌다. */
export const NoReviewPermission: Story = {
  args: {
    ...OTHER_OWNER_ADMIN_ARGS,
    canAssignOwners: false,
    canRemoveOwners: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryAllByRole('button', { name: '반려' })).toHaveLength(0);
    await expect(canvas.queryByRole('button', { name: '전체 승인' })).toBeNull();
    await expect(canvas.queryByRole('button', { name: '전체 반려' })).toBeNull();
    await expect(canvas.queryByRole('button', { name: '최종 내보내기' })).toBeNull();
    // 담당자 카드 — 그 사람 행(담당자 배지)과 배너만 남고 지정·해제 진입점이 없다
    await expect(canvas.getByText('담당자가 검토할 문서입니다')).toBeInTheDocument();
    await expect(canvas.getByText('팀원F')).toBeInTheDocument();
    await expect(canvas.queryByText('채널 관리자')).toBeNull();
    await expect(canvas.queryByRole('button', { name: '담당자 추가하기' })).toBeNull();
    await expect(canvas.queryByRole('button', { name: /팀원F/ })).toBeNull();
    // 열람은 그대로다
    await expect(canvas.getByRole('button', { name: /미리보기/ })).toBeInTheDocument();
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
  },
};

/** 남이 담당자 · 내가 관리자 — 판정은 똑같이 닫히고(관리자는 상위 권한이 아니다) 담당자 관리만 열린다. */
export const OtherOwnerAsAdmin: Story = {
  args: { ...OTHER_OWNER_ADMIN_ARGS },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryByRole('button', { name: '최종 내보내기' })).toBeNull();
    await expect(canvas.getByText('담당자가 검토할 문서입니다')).toBeInTheDocument();
    // 내가 관리자여도 남의 행에는 관리자 배지가 없다 — 서버가 남의 관리자 여부를 주지 않는다
    await expect(canvas.queryByText('채널 관리자')).toBeNull();
    // 담당자 관리 진입점 — + 버튼과 행 팝오버 트리거는 관리자에게만 선다
    await expect(canvas.getByRole('button', { name: '담당자 추가하기' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /팀원F/ })).toBeInTheDocument();
  },
};

/** 담당자 0명 · 내가 관리자 — 판정은 구성원 자격으로 열리고, 내 행이 채널 관리자 배지로 선다. */
export const NoOwnerAsAdmin: Story = {
  args: {
    participants: [{ id: '6', userId: 6, name: '팀원G', isMe: true, roles: ['채널 관리자'] }],
    ownerNotice: 'no-owner',
    canAssignOwners: true,
    canRemoveOwners: true,
    ownerCandidates: [
      { id: '1', label: '팀원F' },
      { id: '2', label: '직원10' },
      { id: '3', label: '이진수' },
      { id: '6', label: '팀원G', suffixLabel: '(나)' },
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 배너는 그대로 선다 — 배지는 내 역할을 말할 뿐 검토자 지정이 아니다
    await expect(canvas.getByText('담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.')).toBeInTheDocument();
    const card = canvas.getByRole('heading', { name: '담당자' }).closest('section')!;
    // 내 행은 채널 관리자 배지만 단다 — '담당자' 텍스트는 제목 하나뿐이라 담당자 행으로 오독되지 않는다
    await expect(within(card).getByText('채널 관리자')).toBeInTheDocument();
    await expect(within(card).getAllByText('담당자')).toHaveLength(1);
    await expect(within(card).getByText('(나)')).toBeInTheDocument();
    // 폴백 행은 해제 팝오버 트리거가 아니다 — 지울 지정이 없다
    await expect(within(card).queryByRole('button', { name: /팀원G/ })).toBeNull();
    await expect(within(card).getByRole('button', { name: '담당자 추가하기' })).toBeInTheDocument();
    // 판정·발행 진입점은 열린 채다
    await expect(canvas.getAllByRole('button', { name: '승인' }).length).toBeGreaterThan(0);
    await expect(canvas.getByRole('button', { name: '최종 내보내기' })).toBeInTheDocument();
  },
};

/** 담당자 0명 · 일반 구성원 — 판정은 똑같이 열리고, 카드는 비고 지정 진입점조차 없다. */
export const NoOwnerAsMember: Story = {
  args: {
    participants: [],
    ownerNotice: 'no-owner',
    canAssignOwners: false,
    canRemoveOwners: false,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('담당자가 지정되지 않아 구성원 누구나 검토할 수 있습니다.')).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '담당자 추가하기' })).toBeNull();
    // 관리자가 아니라 폴백 행도 배지도 없다 — 내 관리자 여부만 서버가 준다
    const card = canvas.getByRole('heading', { name: '담당자' }).closest('section')!;
    await expect(within(card).getAllByText('담당자')).toHaveLength(1);
    await expect(within(card).queryByText('채널 관리자')).toBeNull();
    await expect(canvas.getAllByRole('button', { name: '승인' }).length).toBeGreaterThan(0);
    await expect(canvas.getByRole('button', { name: '최종 내보내기' })).toBeInTheDocument();
  },
};

/** 카드 반려도 곧바로 나가지 않고 사유 입력을 거친다 — 전체 반려와 같은 다이얼로그, 문구만 다르다. */
export const BlockRejectReason: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await userEvent.click(canvas.getAllByRole('button', { name: '반려' })[0]);
    await expect(args.onRejectBlock).toHaveBeenCalledWith(expect.objectContaining({ blockIndex: 0 }));

    const dialog = within(await portal.findByRole('dialog'));
    await expect(dialog.getByText('블록 반려')).toBeInTheDocument();
    await expect(dialog.getByRole('button', { name: '반려' })).toBeDisabled();

    await userEvent.type(dialog.getByRole('textbox', { name: '반려 사유' }), '근거 VOC가 한 건뿐입니다');
    await userEvent.click(dialog.getByRole('button', { name: '반려' }));
    await expect(args.onRejectBlockSubmit).toHaveBeenCalledWith('근거 VOC가 한 건뿐입니다');
  },
};

/**
 * 전체 승인이 돌아온 뒤. 카드마다 승인 판정이 서서 전부 접히고 안건은 큐에 남는다 —
 * 발행은 별도 클릭이라 하단 바가 활성으로 남아야 한다.
 */
export const BulkApproved: Story = {
  args: { entries: entries.map((entry) => ({ ...entry, approved: true })) },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 판정된 카드는 접힌 채로 남는다 — 결정한 블록을 다시 훑을 이유가 없다
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.getAllByRole('button', { name: '펼치기' })).toHaveLength(entries.length);
    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);

    // 안건이 큐에 남아 있어 목록·상세가 그대로다
    await expect(canvas.getByRole('heading', { level: 2, name: selected.title })).toBeInTheDocument();
    await expect(canvas.queryByText('요청된 변경사항이 없어요.')).toBeNull();

    // 발행은 아직 남은 단계다 — 바가 활성으로 서 있어야 흐름이 이어진다
    const publish = canvas.getByRole('button', { name: '최종 내보내기' });
    await expect(publish).toBeEnabled();
    await userEvent.click(publish);
    await expect(args.onPublish).toHaveBeenCalled();
  },
};

/**
 * 담당자 지정·해제 조작 — 추가는 후보 선택과 확인 모달을 거치고, 해제는 행 팝오버에서 나간다.
 * 요청·토스트·권한 판정은 라우트 몫이라 콜백 호출만 본다.
 */
export const OwnerManagement: Story = {
  args: { ...OTHER_OWNER_ADMIN_ARGS },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    // + 버튼 툴팁 — 아이콘+제목 구성이고, 우측 패널이라 앵커 좌측에 선다.
    await userEvent.hover(canvas.getByRole('button', { name: '담당자 추가하기' }));
    const tooltip = (await portal.findByRole('tooltip')).closest('[data-side]') as HTMLElement;
    await expect(tooltip).toHaveAttribute('data-side', 'left');
    await expect(tooltip).toHaveTextContent('담당자 추가하기');
    await expect(tooltip.querySelector('svg')).not.toBeNull();
    await userEvent.unhover(canvas.getByRole('button', { name: '담당자 추가하기' }));

    // 추가 — 후보를 고르고 [추가하기] → 확인 모달의 [확인]까지 가야 지정이 나간다
    await userEvent.click(canvas.getByRole('button', { name: '담당자 추가하기' }));
    // 같은 이름이 좌측 목록 행에도 있어 드롭다운 안으로 좁혀 집는다
    const search = await portal.findByPlaceholderText('담당자 검색');
    const dropdown = within(search.closest('[role="dialog"]') as HTMLElement);
    await userEvent.click(dropdown.getByText('직원10'));
    const addButton = dropdown.getByRole('button', { name: '추가하기' });
    await expect(addButton).toBeEnabled();
    await userEvent.click(addButton);

    await expect(await portal.findByText('담당자를 지정할까요?')).toBeInTheDocument();
    await expect(
      portal.getByText(
        '지정한 담당자가 이 문서의 검토를 맡게 됩니다. 지정 후에는 담당자만 판정하고 내보낼 수 있습니다.',
      ),
    ).toBeInTheDocument();
    await userEvent.click(portal.getByRole('button', { name: '확인' }));
    await expect(args.onAssignOwners).toHaveBeenCalledWith([2]);

    // 모달이 다 내려가야 바깥이 aria-hidden에서 풀린다 — 다음 조작 전에 기다린다
    await waitFor(async () => {
      await expect(portal.queryByText('담당자를 지정할까요?')).toBeNull();
    });

    // 해제 — 담당자 행을 열면 300px 팝오버가 서고, 해제하기가 대상 user_id를 내보낸다
    const ownerRow = canvas.getByRole('button', { name: /팀원F/ });
    // 행 호버 셸 — 패딩 4·radius 8·중립 호버 채움(합성 이벤트는 :hover를 못 깨워 클래스로 잰다).
    await expect(ownerRow.className).toContain('hover:bg-fill-normal-interaction-hover');
    await expect(ownerRow).toHaveClass('p-1', 'rounded-lg');

    await userEvent.click(ownerRow);
    const popoverHeader = await portal.findByText('팀원F 님이 이 문서의 검토 담당자입니다');
    // 팝오버는 앵커 좌측에 선다 — 우측 패널이라 좌측만 화면을 벗어나지 않는다.
    const popover = popoverHeader.closest('[data-side]') as HTMLElement;
    await expect(popover).toHaveAttribute('data-side', 'left');
    await expect(popover.getBoundingClientRect().right).toBeLessThanOrEqual(ownerRow.getBoundingClientRect().left + 1);

    await userEvent.click(portal.getByRole('button', { name: '담당자 해제하기' }));
    await expect(args.onRemoveOwner).toHaveBeenCalledWith(1);
  },
};

/** 반려 사유 입력 자리가 없을 때 — 승인만 남는다. */
export const NoRejectPath: Story = {
  args: { canReject: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByRole('button', { name: '반려' })).toHaveLength(0);
    await expect(canvas.getAllByRole('button', { name: '승인' }).length).toBeGreaterThan(0);
  },
};

/** 전체 반려는 곧바로 나가지 않고 사유 입력을 거친다. */
export const RejectReason: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    await userEvent.click(canvas.getByRole('button', { name: '전체 반려' }));
    await expect(args.onRejectDialogOpenChange).toHaveBeenCalledWith(true);

    const dialog = within(await portal.findByRole('dialog'));
    await expect(dialog.getByRole('button', { name: '전체 반려' })).toBeDisabled();

    await userEvent.type(dialog.getByRole('textbox', { name: '반려 사유' }), '근거 문서가 없습니다');
    await userEvent.click(dialog.getByRole('button', { name: '전체 반려' }));
    await expect(args.onRejectAll).toHaveBeenCalledWith('근거 문서가 없습니다');
  },
};

/**
 * 처리할 변경안이 하나도 없을 때. 상세를 그릴 대상이 없어 중앙·우측을 안내로 갈음한다.
 * 시안이 없는 상태라 대시보드 빈 표의 일러스트·타이포를 그대로 쓴다(디자이너 확인 대상).
 */
export const EmptyQueue: Story = {
  args: { items: [], totalCount: 0, selectedId: null, entries: [], participants: [] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('요청된 변경사항이 없어요.')).toBeInTheDocument();

    // 머리글의 건수는 0으로 남는다 — 목록 자리만 비운다.
    await expect(canvas.getByText('요청된 변경사항')).toBeInTheDocument();
    await expect(canvas.getByText('0')).toBeInTheDocument();

    // 상세·판정 자리가 통째로 빠진다. 껍데기만 남은 화면을 막는 어서션이다.
    await expect(canvas.queryByRole('button', { name: '최종 내보내기' })).toBeNull();
    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryByText('문서 위치')).toBeNull();

    // 필터는 남아야 한다 — 필터로 비운 경우 되돌릴 경로가 여기뿐이다.
    await expect(canvas.getByRole('button', { name: '필터' })).toBeInTheDocument();
  },
};

/** 필터를 걸어 결과가 0건인 경우. 안내 문구는 빈 큐와 가르지 않는다(시안 근거 없음). */
export const EmptyByFilter: Story = {
  args: {
    items: [],
    totalCount: 0,
    selectedId: null,
    entries: [],
    participants: [],
    filters: { channelIds: ['channel-payments'], assigneeIds: [], waitingId: 'all' },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('요청된 변경사항이 없어요.')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '필터' })).toBeInTheDocument();
  },
};

/**
 * 큐 첫 조회를 기다리는 동안. 좌측 목록과 상세 자리가 함께 골격이 된다.
 * 빈 안내가 서면 "처리할 게 없음"으로 읽히므로, 로딩과 빈 상태를 가르는 것이 이 스토리의 핵심이다.
 */
export const ListFirstLoad: Story = {
  args: { items: [], totalCount: 0, selectedId: null, entries: [], participants: [], listPending: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('status', { name: '변경사항 목록 불러오는 중' })).toBeInTheDocument();
    await expect(canvas.getByRole('status', { name: '변경사항 불러오는 중' })).toBeInTheDocument();

    // 빈 안내는 서지 않는다 — 로딩과 "없음"이 같은 시각이면 안 된다.
    await expect(canvas.queryByText('요청된 변경사항이 없어요.')).toBeNull();

    // 좌측 머리글과 필터는 남는다 — 골격이 패널을 통째로 대체하지 않는다.
    await expect(canvas.getByText('요청된 변경사항')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '필터' })).toBeInTheDocument();
  },
};

/** 목록은 왔고 고른 안건의 상세만 기다리는 동안. 좌측 행은 실물이고 중앙만 골격이다. */
export const DetailFirstLoad: Story = {
  args: { detailPending: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 좌측 행은 실물이다 — 목록에만 있는 다른 안건 제목으로 집는다.
    await expect(canvas.getByText('환불 문서 병합 제안')).toBeInTheDocument();
    await expect(canvas.getByRole('status', { name: '변경사항 불러오는 중' })).toBeInTheDocument();
    await expect(canvas.queryByRole('status', { name: '변경사항 목록 불러오는 중' })).toBeNull();

    // 상세 본문·판정 진입점은 아직 서지 않는다.
    await expect(canvas.queryByText('이렇게 바뀌었어요')).toBeNull();
    await expect(canvas.queryByRole('heading', { level: 2, name: selected.title })).toBeNull();
  },
};
