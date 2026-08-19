import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ReviewPublishBar from './ReviewPublishBar';

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/ReviewPublishBar',
  component: ReviewPublishBar,
  tags: ['autodocs'],
  args: { onPublish: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17762-105531',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17762:105531',
      },
      viewport: { width: 700, height: 120 },
      states: ['default', 'no-review-permission'],
      reuseNotes: [
        '전체 승인/거절은 MVP 제외라 이 바에는 "최종 내보내기" 단일 액션만 있다 — 판정은 블록 카드 단위다.',
      ],
      dataNotes: [
        'canReview=false면 바 자체를 렌더하지 않는다 — 액션이 하나뿐이라 버튼만 빼면 빈 띠가 남는다. 값은 서버가 계산한 can_review다.',
        '"최종 내보내기"의 백엔드 대응은 미정이라 콜백만 뚫려 있다(선행 approve 전제 문제, design-request #3).',
      ],
      layoutNotes: ['폭은 상세 패널이 준다 — 바에 px를 박지 않는다.'],
    }),
  },
} satisfies Meta<typeof ReviewPublishBar>;

export default meta;
type Story = StoryObj<typeof ReviewPublishBar>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '최종 내보내기' }));
    await expect(args.onPublish).toHaveBeenCalled();
  },
};

/** 검토 권한 없음 — 발행 진입점이 화면에서 사라진다. */
export const NoReviewPermission: Story = {
  args: { canReview: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByRole('button')).toBeNull();
    await expect(canvasElement.textContent).not.toContain('최종 내보내기');
  },
};
