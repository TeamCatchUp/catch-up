import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorBackLink from './ConnectorBackLink';

const meta = {
  title: 'Compositions/Admin/Integrations/ConnectorBackLink',
  component: ConnectorBackLink,
  tags: ['autodocs'],
  args: { onBack: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134098',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134098',
      },
      viewport: { width: 320, height: 120 },
      states: ['default'],
      dataNotes: [
        'Figma는 Text Button의 size=large_이전페이지 변형인데 코드 Text Button에는 그 크기가 없다.',
        'size="md"에 heading-small 타이포와 gap만 덮어 맞췄다.',
      ],
    }),
  },
} satisfies Meta<typeof ConnectorBackLink>;

export default meta;

type Story = StoryObj<typeof ConnectorBackLink>;

export const Default: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal p-6">
      <ConnectorBackLink {...args} />
    </div>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: '커넥터 전체 보기' }));
    await expect(args.onBack).toHaveBeenCalled();
  },
};
