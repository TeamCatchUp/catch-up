import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import {
  BASE_WIKI_BLOCKS,
  PROPOSED_WIKI_BLOCKS,
  reviewProposalDetail,
  withBlockVerdict,
} from '../../../fixtures/llmWikiDiffFixtures';
import type { DocumentBreadcrumb } from '../../../types/llmWikiModel';
import { composeProposalPreview } from './composeProposalPreview';
import ProposalPreviewPage from './ProposalPreviewPage';

const [MODIFIED, ADDED] = PROPOSED_WIKI_BLOCKS;

const BREADCRUMBS: readonly DocumentBreadcrumb[] = [
  { kind: 'channel', label: '결제' },
  { kind: 'folder', label: '승인·실패 처리' },
  { kind: 'document', label: '결제 재시도 정책' },
];

const meta = {
  title: 'Screens/LLM Wiki/ProposalPreviewPage',
  component: ProposalPreviewPage,
  tags: ['autodocs'],
  args: {
    title: '결제 재시도 정책',
    owners: [],
    timeLabel: '12시간 전',
    breadcrumbs: BREADCRUMBS,
    items: composeProposalPreview(reviewProposalDetail()),
    onBreadcrumbClick: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      viewport: { width: 1200, height: 800 },
      states: ['undecided', 'block-rejected', 'new-document'],
      reuseNotes: [
        '셸·본문 부품(WikiDocumentShell·DocumentSection·DocumentTable)을 문서 열람 화면과 함께 쓴다 — 검토자가 승인한 화면과 발행 뒤 화면이 달라지면 안 된다.',
        'WikiDocumentPage를 그대로 쓰지 않는다 — 그 계약(WikiDocumentData)은 revisionId·publishedAt을 요구하는 "발행된 판"이라 미발행 제안본에 맞출 값이 없다. 공유는 렌더 부품까지이고 layout 순회는 화면마다 따로다.',
      ],
      dataNotes: [
        '재료는 검토 큐 상세(GET /knowledge-review/queue/{proposal_id}) 하나다 — 발행판 조회를 타지 않아 발행된 적 없는 문서도 열린다.',
        '합성 규칙: 승인·미판정은 제안 블록, 반려는 발행판 블록으로 되돌리고 되돌릴 자리가 없으면(신규 블록) 뺀다.',
        '백엔드 발행(_assemble)은 반려 블록을 발행판으로 되돌리지 않고 통째로 뺀다 — 미리보기의 되돌림은 사용자 확정 규칙이라 그 자리에서 갈린다.',
        '발행 시각 자리에는 미리보기 표기가 선다 — 아직 판이 아니라 실을 시각이 없다.',
        '본문 위 안내 배너는 시안 없는 자작이다(사용자 확정 문구) — 담당자 카드 안내 배너 패턴을 그대로 쓴다.',
      ],
      layoutNotes: ['본문 폭 max-w-260·좌우 24는 문서 열람 화면과 같은 값이다.'],
    }),
  },
} satisfies Meta<typeof ProposalPreviewPage>;

export default meta;
type Story = StoryObj<typeof ProposalPreviewPage>;

/** 판정 전 — 제안 블록이 양식 순서 그대로 실린다. */
export const Undecided: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('heading', { level: 1, name: '결제 재시도 정책' })).toBeInTheDocument();
    await expect(canvas.getByText('담당자 없음')).toBeInTheDocument();
    await expect(canvas.getByText('12시간 전')).toBeInTheDocument();

    // 양식 순서(PG → 재시도)가 저장 순서(재시도 → PG)를 이긴다
    const headings = canvas.getAllByRole('heading', { level: 2 }).map((node) => node.textContent);
    await expect(headings).toEqual(['PG 점검 시간 예외', '재시도 정책']);

    // 제안 본문이 실린다 — 발행판의 "한 번 더"가 아니다
    await expect(canvasElement.textContent).toContain('세 번까지');
    await expect(canvasElement.textContent).not.toContain('한 번 더');

    // 열람 전용이다 — 판정·편집 진입점이 없다
    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryByRole('textbox')).toBeNull();

    // 이전 마디는 버튼이고 클릭이 밖으로 나간다 — 새 탭에서도 채널·폴더로 갈 수 있어야 한다
    await userEvent.click(canvas.getByRole('button', { name: '결제' }));
    await expect(args.onBreadcrumbClick).toHaveBeenCalledWith({ kind: 'channel', label: '결제' }, 0);
  },
};

/** 블록 판정을 반영한 모습 — 반려한 수정은 발행판으로 되돌아가고 반려한 신규 블록은 빠진다. */
export const BlockRejected: Story = {
  args: {
    items: composeProposalPreview(
      reviewProposalDetail({ blocks: [withBlockVerdict(MODIFIED, 'rejected'), withBlockVerdict(ADDED, 'rejected')] }),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 되돌릴 자리가 없는 신규 블록은 통째로 빠진다
    const headings = canvas.getAllByRole('heading', { level: 2 }).map((node) => node.textContent);
    await expect(headings).toEqual(['재시도 정책']);

    // 본문은 발행판 산문으로 돌아간다
    await expect(canvasElement.textContent).toContain(BASE_WIKI_BLOCKS[0].narrative!);
    await expect(canvasElement.textContent).not.toContain('세 번까지');
  },
};

/** 발행된 적 없는 문서 — 발행판이 없어도 제안본을 그대로 읽는다. */
export const NewDocument: Story = {
  args: {
    items: composeProposalPreview(
      reviewProposalDetail({
        baseRevisionId: null,
        baseBlocks: [],
        changes: [
          { kind: 'added', blockIndex: 0, baseBlockIndex: null },
          { kind: 'added', blockIndex: 1, baseBlockIndex: null },
        ],
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const headings = canvas.getAllByRole('heading', { level: 2 }).map((node) => node.textContent);
    await expect(headings).toEqual(['PG 점검 시간 예외', '재시도 정책']);
    await expect(canvas.getByText('12시간 전')).toBeInTheDocument();
  },
};
