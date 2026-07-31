import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorDetailSkeleton from './ConnectorDetailSkeleton';

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectorDetailSkeleton',
  component: ConnectorDetailSkeleton,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['detail-loading'],
      dataNotes: [
        'Figma에 로딩 프레임이 없다. 디자인 시스템 Skeleton 승계로 사용자 승인된 상태.',
        '텍스트를 포함하지 않는다 — 새 카피 0건 제약.',
      ],
      reuseNotes: ['EmbeddingModal이 이미 같은 shared Skeleton을 사용한다.'],
    }),
  },
} satisfies Meta<typeof ConnectorDetailSkeleton>;

export default meta;

type Story = StoryObj<typeof ConnectorDetailSkeleton>;

export const Playground: Story = {
  render: () => (
    <div className="bg-fill-normal-normal flex min-h-96 w-160 flex-col p-6">
      <ConnectorDetailSkeleton />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByLabelText('연동 정보 불러오는 중')).toBeInTheDocument();
  },
};
