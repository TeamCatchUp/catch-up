import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import {
  BASE_WIKI_BLOCKS,
  PROPOSED_BLOCK_CHANGES,
  PROPOSED_WIKI_BLOCKS,
} from '../../../fixtures/llmWikiDiffFixtures';
import { buildBlockDiff } from '../../../utils/diff/buildBlockDiff';
import BlockDiffSection from './BlockDiffSection';

const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/BlockDiffSection',
  component: BlockDiffSection,
  tags: ['autodocs'],
  args: { onPreview: fn(), onApprove: fn(), onReject: fn() },
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
        '미리보기 버튼(8/13 시안 — 구 "직접 수정" 자리)의 실제 동작은 미정 — 콜백만 뚫려 있다. 제안본 접근에는 proposalId가 필수다(documentId만으로는 제안본을 못 가져온다). 개별 블록 수정은 MVP 제외라 카드에는 진입점이 없다.',
        'canReview는 카드로 그대로 내려간다 — 섹션 헤더의 미리보기는 열람이라 권한과 무관하다.',
      ],
      layoutNotes: ['시안 폭 654는 상세 패널 것이라 px를 박지 않는다 — 스토리 뷰포트 700이 슬롯 역할.'],
    }),
  },
} satisfies Meta<typeof BlockDiffSection>;

export default meta;
type Story = StoryObj<typeof BlockDiffSection>;

/** 검토 권한 없음 — 모든 카드에서 승인·반려가 사라지고 미리보기만 남는다. */
export const NoReviewPermission: Story = {
  args: { entries, canReview: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByRole('button', { name: '승인' })).toHaveLength(0);
    await expect(canvas.queryAllByRole('button', { name: '반려' })).toHaveLength(0);
    // 열람 진입점은 남는다
    await expect(canvas.getByRole('button', { name: /미리보기/ })).toBeInTheDocument();
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
  },
};

export const Default: Story = {
  args: { entries },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('수정 내용')).toBeInTheDocument();
    await expect(canvas.getByText(String(entries.length))).toBeInTheDocument();
    await expect(canvas.getByText('작성자가 변경한 내용입니다.')).toBeInTheDocument();

    // 카드 3종이 모두 렌더된다
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('PG 점검 시간 예외')).toBeInTheDocument();
    await expect(canvas.getByText('수동 재시도 안내')).toBeInTheDocument();

    // 헤더 전역 버튼은 미리보기 하나뿐이다 — 개별 블록 수정은 범위 밖이라 카드에 없다.
    await userEvent.click(canvas.getByRole('button', { name: /미리보기/ }));
    await expect(args.onPreview).toHaveBeenCalled();
    await expect(canvas.queryByRole('button', { name: '이 블록 수정' })).toBeNull();
  },
};
