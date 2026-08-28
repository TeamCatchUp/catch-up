import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorEmptyState from './ConnectorEmptyState';

const meta = {
  title: 'Compositions/Admin/Integrations/States/ConnectorEmptyState',
  component: ConnectorEmptyState,
  tags: ['autodocs'],
  args: { onStart: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17122-112578',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17122:112578',
      },
      viewport: { width: 1040, height: 741 },
      states: ['default'],
      layoutNotes: [
        '일러스트는 이미지가 아니라 원 2개 + 로고 칩 5개의 절대 배치다.',
        '로고 4개는 바깥 원(r=237), GitHub만 안쪽 원(r=175) 위에 놓인다.',
        '원의 stroke는 위→아래로 사라지는 그라디언트라 mask-image로 재현했다.',
      ],
      dataNotes: ['CTA 라벨은 Figma 원문이 "커텍터 연결하기"(오타)라 사용자 확인 후 "커넥터"로 교정했다.'],
    }),
  },
} satisfies Meta<typeof ConnectorEmptyState>;

export default meta;

type Story = StoryObj<typeof ConnectorEmptyState>;

export const Default: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex h-185 w-260 p-8">
      <ConnectorEmptyState {...args} />
    </div>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('아직 연결된 협업툴이 없어요')).toBeInTheDocument();
    await expect(canvas.getByText(/팀에 흩어진 대화와 문서를 한데 모아/)).toBeInTheDocument();

    // 장식은 스크린리더에서 감춘다
    const decoration = canvasElement.querySelector('[aria-hidden="true"]');
    await expect(decoration).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '커넥터 연결하기' }));
    await expect(args.onStart).toHaveBeenCalled();
  },
};
