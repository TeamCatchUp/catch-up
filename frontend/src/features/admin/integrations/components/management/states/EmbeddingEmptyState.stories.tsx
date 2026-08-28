import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingEmptyState from './EmbeddingEmptyState';

const meta = {
  title: 'Compositions/Admin/Integrations/States/EmbeddingEmptyState',
  component: EmbeddingEmptyState,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17306-82275',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17306:82275',
      },
      viewport: { width: 716, height: 360 },
      states: ['default'],
      dataNotes: [
        '상태 감사가 UNKNOWN(구현 승계)으로 오판정했던 항목이다. Figma 17306:82007에 프레임이 있다.',
        '현행 코드의 "연동된 항목이 없습니다."가 아니라 "임베딩한 채널이 없습니다"가 승인 문구다.',
      ],
      layoutNotes: ['요약 카드는 그대로 남고 표 자리만 이것으로 교체된다.'],
    }),
  },
} satisfies Meta<typeof EmbeddingEmptyState>;

export default meta;

type Story = StoryObj<typeof EmbeddingEmptyState>;

export const Default: Story = {
  render: () => (
    <div className="bg-fill-normal-normal w-179">
      <EmbeddingEmptyState />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('임베딩한 채널이 없습니다')).toBeInTheDocument();

    // 일러스트는 장식이라 alt가 비어 있다 — role로는 못 찾으므로 직접 집는다
    const illustration = canvasElement.querySelector('img');
    await expect(illustration).toBeInTheDocument();

    if (illustration && !illustration.complete) {
      await new Promise((resolve) => {
        illustration.addEventListener('load', resolve, { once: true });
        illustration.addEventListener('error', resolve, { once: true });
      });
    }
    await expect(illustration?.naturalWidth ?? 0).toBeGreaterThan(0);
  },
};
