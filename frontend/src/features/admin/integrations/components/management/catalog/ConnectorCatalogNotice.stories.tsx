import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorCatalogNotice from './ConnectorCatalogNotice';

const meta = {
  title: 'Compositions/Admin/Integrations/Connect/ConnectorCatalogNotice',
  component: ConnectorCatalogNotice,
  tags: ['autodocs'],
  args: { onLearnMore: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16966-66318',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16966:66318',
      },
      viewport: { width: 1040, height: 120 },
      states: ['default', 'narrow'],
      tokenNotes: ['배경 #F7F7F8 = bg-fill-normal-strong, 본문 #6D7882 = text-text-normal-alternative.'],
    }),
  },
} satisfies Meta<typeof ConnectorCatalogNotice>;

export default meta;

type Story = StoryObj<typeof ConnectorCatalogNotice>;

export const Default: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal w-244 p-6">
      <ConnectorCatalogNotice {...args} />
    </div>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(
      canvas.getByText('연결은 관리자만 할 수 있어요. 데이터는 읽기 전용으로 안전하게 동기화돼요'),
    ).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: /연결에 대해 더 자세히 알아보기/ }));
    await expect(args.onLearnMore).toHaveBeenCalled();
  },
};

/** 2단 배치의 우측 컬럼(716px)에서도 한 줄을 유지하는지 */
export const Narrow: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal w-179 p-6">
      <ConnectorCatalogNotice {...args} />
    </div>
  ),
};
