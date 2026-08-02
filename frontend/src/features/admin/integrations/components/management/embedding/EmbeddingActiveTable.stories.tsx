import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingActiveTable from './EmbeddingActiveTable';

const ITEMS = Array.from({ length: 5 }, (_, i) => ({
  id: `a-${i}`,
  target: `채널명 text text text text text texttexttexttexttext ${i}`,
}));

const meta = {
  title: 'Compositions/Admin/Integrations/EmbeddingActiveTable',
  component: EmbeddingActiveTable,
  tags: ['autodocs'],
  args: { service: 'slack', items: ITEMS },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17125-114635',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17125:114635',
      },
      viewport: { width: 716, height: 300 },
      states: ['running', 'none'],
      reuseNotes: ['히스토리 표와 같은 4열 헤더를 공유한다 (EmbeddingTableHeader).'],
    }),
  },
} satisfies Meta<typeof EmbeddingActiveTable>;

export default meta;

type Story = StoryObj<typeof EmbeddingActiveTable>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Running: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingActiveTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('임베딩 대상')).toBeInTheDocument();
    await expect(canvas.getByText('임베딩 상태')).toBeInTheDocument();
    await expect(canvas.getByText('실행 시각')).toBeInTheDocument();
    await expect(canvas.getAllByText('진행중')).toHaveLength(5);
    await expect(canvas.getAllByRole('row')).toHaveLength(6); // 헤더 1 + 본문 5
  },
};

/** 진행중이 없으면 섹션 자체를 렌더하지 않는다 */
export const None: Story = {
  args: { items: [] },
  render: (args) => (
    <Frame>
      <EmbeddingActiveTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.queryByRole('table')).not.toBeInTheDocument();
  },
};
