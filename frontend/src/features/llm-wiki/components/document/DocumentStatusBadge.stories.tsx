import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import DocumentStatusBadge from './DocumentStatusBadge';

const meta = {
  title: 'Compositions/LLM Wiki/Document/DocumentStatusBadge',
  component: DocumentStatusBadge,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17698-184150',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17698:184150',
      },
      viewport: { width: 200, height: 80 },
      states: ['reviewed', 'unknown-status'],
      dataNotes: [
        '디자인 확정 배지는 "검토 완료" 1종뿐이다. contested·pending_review 배지는 발명 금지(감사 계약).',
        '미지 status 값이 오면 배지를 렌더하지 않는다 — 임의 시각화가 승인된 디자인처럼 남는 것을 막는다.',
      ],
      tokenNotes: [
        '배경 #D9F7EB = bg-accent-green-neutral, 글자 #00985A = text-accent-green-default, radius/lg = rounded-lg, body(md)/small = text-body-small.',
        '색·타이포는 shared Badge의 success 변형을 그대로 쓰고, 기하(반경·패딩)만 Figma 값으로 덮는다.',
        'icon/verified(17698:184151)는 Figma export를 fill="currentColor"로 정규화해 Badge 글자색을 상속한다 — 다크 모드에서 accent-green이 바뀌어도 따라간다.',
      ],
      layoutNotes: [
        'Figma 배지 프레임(17698:184150)은 100×31 고정이지만 라벨 길이에 따라 늘어나는 hug 성격이라 폭을 고정하지 않는다. 높이 31 = py 4 + 라인박스 22.5 + py 4.',
        '가로 구성 8(pl) + 20(icon) + 8(gap) + 56(text) + 8(pr) = 100 — 프레임 폭과 정확히 일치하므로 hug이 맞다. gap 8 = gap-2, 아이콘 20 = size-5.',
      ],
    }),
  },
} satisfies Meta<typeof DocumentStatusBadge>;

export default meta;
type Story = StoryObj<typeof DocumentStatusBadge>;

export const Reviewed: Story = {
  args: { status: 'reviewed' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const badge = canvas.getByText('검토 완료');
    await expect(badge).toBeInTheDocument();

    // shared Badge 기본값은 rounded-full이다. tailwind-merge가 이 덮어쓰기를 놓치면
    // 알약 모양으로 조용히 되돌아가므로 Figma의 radius/lg(8px)를 직접 못박는다.
    await expect(getComputedStyle(badge).borderRadius).toBe('8px');

    // Figma 배지는 icon/verified를 동반한다. aria-hidden이라 접근성 트리에 없으므로 DOM으로 확인한다.
    const icon = badge.querySelector('svg');
    await expect(icon).not.toBeNull();
    await expect(icon).toHaveAttribute('aria-hidden');
    // Figma export 원본은 fill="#00985A"였다. 재export로 hex가 되살아나면 라이트 모드에서는
    // 값이 우연히 같아 눈에 띄지 않고 다크 모드에서만 어긋나므로, 계산된 색이 아니라 속성을 못박는다.
    await expect(icon!.querySelector('path')).toHaveAttribute('fill', 'currentColor');
  },
};

/** 확정 디자인이 없는 status는 배지를 만들지 않고 아무것도 렌더하지 않는다 */
export const UnknownStatusRendersNothing: Story = {
  args: { status: 'contested' },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).queryByText(/./)).toBeNull();
  },
};
