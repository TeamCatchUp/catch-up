import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { BASE_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES, PROPOSED_WIKI_BLOCKS } from '../../../fixtures/llmWikiDiffFixtures';
import { buildBlockDiff } from '../../../utils/diff/buildBlockDiff';
import BlockDiffSection from './BlockDiffSection';

const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/BlockDiffSection',
  component: BlockDiffSection,
  tags: ['autodocs'],
  args: { onApprove: fn(), onReject: fn(), onApproveAll: fn(), onRejectAll: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
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
      viewport: { width: 700, height: 900 },
      states: ['default', 'no-review-permission'],
      dataNotes: [
        '건수 배지는 entries.length다 — 시안의 "12"는 목업 값이고 계약이 아니다.',
        '변경 0건 빈 상태 스토리는 만들지 않는다(MISSING — 감사 계약). 검토 큐 상세 레이아웃 조립은 다음 단계다.',
        '전체 승인·반려는 판정이 시작된 뒤에도 잠그지 않는다 — 서버가 409로 거절하고 그 메시지를 토스트로 보인다.',
        '반려는 사유가 필수라 버튼이 곧바로 요청을 내지 않고 사유 입력 다이얼로그를 연다.',
        '미리보기는 헤더 액션으로 옮겨갔다 — 이 섹션은 판정 진입점만 든다.',
      ],
      layoutNotes: ['시안 폭 654는 상세 패널 것이라 px를 박지 않는다 — 스토리 뷰포트 700이 슬롯 역할.'],
    }),
  },
} satisfies Meta<typeof BlockDiffSection>;

export default meta;
type Story = StoryObj<typeof BlockDiffSection>;

/** 검토 권한 없음 — 카드의 승인·반려와 헤더의 전체 판정이 함께 사라진다. */
export const NoReviewPermission: Story = {
  args: { entries, canReview: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryAllByRole('button', { name: '반려' })).toHaveLength(0);
    await expect(canvas.queryByRole('button', { name: '전체 승인' })).toBeNull();
    await expect(canvas.queryByRole('button', { name: '전체 반려' })).toBeNull();
    // 열람은 그대로다
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
  },
};

export const Default: Story = {
  args: { entries },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('변경 내용')).toBeInTheDocument();
    await expect(canvas.getByText(String(entries.length))).toBeInTheDocument();
    await expect(canvas.getByText('작성자가 변경한 내용입니다.')).toBeInTheDocument();

    // 카드 3종이 모두 렌더된다
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('PG 점검 시간 예외')).toBeInTheDocument();
    await expect(canvas.getByText('수동 재시도 안내')).toBeInTheDocument();

    // 헤더의 전역 액션은 전체 반려·전체 승인 둘뿐이다
    await userEvent.click(canvas.getByRole('button', { name: '전체 반려' }));
    await expect(args.onRejectAll).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: '전체 승인' }));
    await expect(args.onApproveAll).toHaveBeenCalled();

    await expect(canvas.queryByRole('button', { name: /미리보기/ })).toBeNull();
    await expect(canvas.queryByRole('button', { name: '이 블록 수정' })).toBeNull();
  },
};
