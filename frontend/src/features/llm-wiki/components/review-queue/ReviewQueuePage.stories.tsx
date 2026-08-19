import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

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

const meta = {
  title: 'Screens/LLM Wiki/ReviewQueuePage',
  component: ReviewQueuePage,
  tags: ['autodocs'],
  /** 선택 행은 소비처(라우트)가 든다 — 스토리는 그 자리를 로컬 state로 대신한다. */
  render: function ReviewQueueStory(args) {
    const [selectedId, setSelectedId] = useState(args.selectedId);

    return (
      <div className="h-225">
        <ReviewQueuePage
          {...args}
          selectedId={selectedId}
          onSelectItem={(id) => {
            args.onSelectItem(id);
            setSelectedId(id);
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
    locationBreadcrumbs: [
      { kind: 'channel', label: '결제' },
      { kind: 'folder', label: '승인·실패 처리' },
    ],
    title: selected.title,
    waitingLabel: selected.waitingLabel,
    summary: '재시도 한도가 1회에서 3회로 늘고 PG 점검 시간 예외가 추가되었습니다.',
    participants: [{ id: '1', name: '팀원F', role: '리뷰어' }],
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
        'undecided-blocks',
        'no-review-permission',
        'no-reject-path',
        'empty-queue',
        'empty-by-filter',
      ],
      reuseNotes: [
        'ReviewQueueListHeader·ReviewQueueRow·ReviewQueueFilterDropdown·WikiPageHeader(detail)·ChangeSummaryCard·BlockDiffSection·DocumentLocationCard·ReviewParticipantsCard·ReviewPublishBar를 조립만 한다.',
      ],
      dataNotes: [
        '화면은 데이터를 props로만 받는다 — 큐·상세 조회와 판정·발행 요청은 라우트가 낸다. 스토리는 MSW 없이 fixture를 주입한다.',
        'diff 카드 짝짓기는 서버 block_changes가 정한다. 프론트는 자리만 따라가고 단어 강조만 만든다 — 같은 안건이 소비자마다 다르게 보이지 않기 위해서다.',
        '발행 버튼은 미판정 블록이 하나라도 남으면 잠긴다. 변경 없는 블록도 판정 대상이라 카드가 없는 블록이 잠금을 유지할 수 있다 — 일괄 처리(undecided) UI는 시안이 없어 만들지 않았다.',
        '반려는 사유가 필수인데 사유 입력 시안이 없다 — 진입점을 닫아 보낼 수 없는 요청을 막는다(NoRejectPath). 시안이 오면 canReject만 켠다.',
        '채널·담당자 축은 서버가 하나씩만 받는다 — 둘 이상 고르면 파라미터로 나가지 않고 받은 쪽에서 좁힌다. 좁히기는 라우트가 맡고 화면은 관여하지 않는다.',
        '빈 큐는 시안이 없다(감사 MISSING·높음). 새 시각을 만들지 않고 대시보드 빈 표와 같은 일러스트·타이포를 쓰며, 필터 결과 0건도 같은 안내다 — 문구를 가르는 근거가 없다. 디자이너 확인 대상.',
        '목록이 비면 좌측 머리글과 필터는 남는다 — 필터로 비운 경우 되돌릴 경로가 사라지면 안 된다.',
        '로딩·에러 시각은 시안이 없어 만들지 않는다 — 데이터가 없으면 상세 자리가 빈 채로 남는다.',
      ],
      layoutNotes: [
        '좌 300 · 우 350 고정, 중앙이 남는 폭을 흡수한다. 높이는 셸이 준다 — 스토리가 900 슬롯을 흉내낸다.',
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

    // 중앙 — 요약과 diff 카드 3장
    await expect(canvas.getByText('이렇게 바뀌었어요')).toBeInTheDocument();
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('PG 점검 시간 예외')).toBeInTheDocument();
    await expect(canvas.getByText('수동 재시도 안내')).toBeInTheDocument();

    // 승인은 판정 경로 키를 그대로 들고 나간다 — 낙관적 잠금의 재료다
    await userEvent.click(canvas.getAllByRole('button', { name: '승인' })[0]);
    await expect(args.onApproveBlock).toHaveBeenCalledWith(
      expect.objectContaining({ blockIndex: 0, blockContentHash: expect.stringMatching(/^sha256:/) }),
    );

    await userEvent.click(canvas.getByRole('button', { name: '최종 내보내기' }));
    await expect(args.onPublish).toHaveBeenCalled();

    // 다른 행을 고르면 선택이 옮겨간다
    await userEvent.click(canvas.getByText('환불 문서 병합 제안'));
    await expect(args.onSelectItem).toHaveBeenCalledWith('proposal-merge-refund');
  },
};

/** 미판정 블록이 남은 상태 — 발행 버튼이 잠긴다. */
export const UndecidedBlocks: Story = {
  args: { publishDisabled: true },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 잠긴 버튼은 pointer-events가 없어 클릭 자체가 닿지 않는다
    await expect(canvas.getByRole('button', { name: '최종 내보내기' })).toBeDisabled();
    await expect(args.onPublish).not.toHaveBeenCalled();
  },
};

/** 검토 권한 없음 — 판정·발행 진입점이 화면에서 사라진다. */
export const NoReviewPermission: Story = {
  args: { canReview: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryAllByRole('button', { name: '반려' })).toHaveLength(0);
    await expect(canvas.queryByRole('button', { name: '최종 내보내기' })).toBeNull();
    // 열람은 그대로다
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
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

/**
 * 처리할 변경안이 하나도 없을 때. 상세를 그릴 대상이 없어 중앙·우측을 안내로 갈음한다.
 * 시안이 없는 상태라 대시보드 빈 표의 일러스트·타이포를 그대로 쓴다(디자이너 확인 대상).
 */
export const EmptyQueue: Story = {
  args: { items: [], totalCount: 0, selectedId: null, entries: [], participants: [] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('요청된 변경사항이 없어요')).toBeInTheDocument();

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

    await expect(canvas.getByText('요청된 변경사항이 없어요')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '필터' })).toBeInTheDocument();
  },
};
