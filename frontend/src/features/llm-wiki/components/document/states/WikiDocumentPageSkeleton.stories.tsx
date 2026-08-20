import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import WikiDocumentPageSkeleton from './WikiDocumentPageSkeleton';

const meta = {
  title: 'Screens/LLM Wiki/States/WikiDocumentPageSkeleton',
  component: WikiDocumentPageSkeleton,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      viewport: { width: 1200, height: 900 },
      states: ['first-load'],
      dataNotes: [
        '문서 열람이 발행판을 기다리는 동안 서는 골격이다 — 제목·발행 시각 줄과 본문 문단 3덩이를 근사한다.',
        '로딩 시안이 없어 전량 자작이다(사용자 확정). 미발행 404(ARTIFACT_NOT_PUBLISHED)는 로딩이 아니라 이 골격이 서지 않는다 — 토스트만 뜨고 화면은 비어 있다.',
      ],
      layoutNotes: [
        '헤더 h-13, 본문 max-w-260·px-6 py-9·gap-6은 데이터 화면과 같은 값이다 — 로드 후 글이 좌우로 움직이지 않는다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiDocumentPageSkeleton>;

export default meta;
type Story = StoryObj<typeof WikiDocumentPageSkeleton>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const status = canvas.getByRole('status', { name: '문서 불러오는 중' });

    // 본문 폭 상한(1040)은 데이터 화면과 같은 값이라 로드 후 글 좌우가 움직이지 않는다.
    await expect(status.getBoundingClientRect().width).toBeLessThanOrEqual(1040);

    // 승인되지 않은 카피를 만들지 않는다 — 골격에 글자가 없다.
    await expect(status.textContent).toBe('');
  },
};
