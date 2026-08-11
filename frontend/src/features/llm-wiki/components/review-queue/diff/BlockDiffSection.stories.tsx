import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS } from '../../../fixtures/llmWikiDiffFixtures';
import { computeBlockDiff } from '../../../utils/diff/computeBlockDiff';
import BlockDiffSection from './BlockDiffSection';

const entries = computeBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS);

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/BlockDiffSection',
  component: BlockDiffSection,
  tags: ['autodocs'],
  args: { onEditDocument: fn(), onApprove: fn(), onReject: fn() },
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
      states: ['default'],
      dataNotes: [
        '건수 배지는 entries.length다 — 시안의 "12"는 목업 값이고 계약이 아니다.',
        '변경 0건 빈 상태 스토리는 만들지 않는다(MISSING — 감사 계약). 검토 큐 상세 레이아웃 조립은 다음 단계다.',
        '직접 수정 버튼의 실제 동작은 미정 — 콜백만 뚫려 있다. 편집 대상은 제안본(blocks[])으로 확정됐고(8/10) 진입에는 proposalId가 필수다(documentId만으로는 제안본을 못 가져온다). 개별 블록 수정은 MVP 제외라 카드에는 진입점이 없다.',
      ],
      layoutNotes: ['시안 폭 654는 상세 패널 것이라 px를 박지 않는다 — 스토리 뷰포트 700이 슬롯 역할.'],
    }),
  },
} satisfies Meta<typeof BlockDiffSection>;

export default meta;
type Story = StoryObj<typeof BlockDiffSection>;

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

    // 편집 진입점은 섹션 헤더의 "직접 수정" 하나뿐이다 — 개별 블록 수정은 범위 밖이라 카드에 없다.
    await userEvent.click(canvas.getByRole('button', { name: '직접 수정' }));
    await expect(args.onEditDocument).toHaveBeenCalled();
    await expect(canvas.queryByRole('button', { name: '이 블록 수정' })).toBeNull();
  },
};
