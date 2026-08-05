import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorCatalog from './ConnectorCatalog';

const meta = {
  title: 'Compositions/Admin/Integrations/Connect/ConnectorCatalog',
  component: ConnectorCatalog,
  tags: ['autodocs'],
  args: { connectedServices: [], onConnect: fn(), onLearnMore: fn() },
  argTypes: {
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134207',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134207',
      },
      viewport: { width: 1040, height: 760 },
      states: ['none-connected', 'partially-connected', 'all-connected', 'two-column'],
      layoutNotes: [
        '컨테이너 976 → 3열(314.67), 716 → 2열(350). gap 16.',
        '빈 상태에서는 전폭(3열), 연동됨 목록이 있으면 우측 컬럼(2열)이다.',
      ],
    }),
  },
} satisfies Meta<typeof ConnectorCatalog>;

export default meta;

type Story = StoryObj<typeof ConnectorCatalog>;

/** 전폭 — 카테고리 3개 · 카드 5개가 3열로 */
export const NoneConnected: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal w-260 p-8">
      <ConnectorCatalog {...args} />
    </div>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('연결 찾기')).toBeInTheDocument();
    await expect(canvas.getByText('워크스페이스에서 사용 가능한 연결 살펴보기')).toBeInTheDocument();

    // 카테고리 3종이 Figma 순서대로
    await expect(canvas.getByText('커뮤니케이션')).toBeInTheDocument();
    await expect(canvas.getByText('문서 · 지식')).toBeInTheDocument();
    await expect(canvas.getByText('개발 · 이슈 관리')).toBeInTheDocument();

    // 5개 모두 연결 가능
    await expect(canvas.getAllByRole('button', { name: '연결' })).toHaveLength(5);

    await userEvent.click(canvas.getAllByRole('button', { name: '연결' })[0]);
    await expect(args.onConnect).toHaveBeenCalled();
  },
};

export const PartiallyConnected: Story = {
  args: { connectedServices: ['slack', 'jira'] },
  render: (args) => (
    <div className="bg-fill-normal-normal w-260 p-8">
      <ConnectorCatalog {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getAllByRole('button', { name: /연결됨/ })).toHaveLength(2);
    await expect(canvas.getAllByRole('button', { name: '연결' })).toHaveLength(3);
  },
};

export const AllConnected: Story = {
  args: { connectedServices: ['slack', 'jira', 'github', 'confluence', 'channel_talk'] },
  render: (args) => (
    <div className="bg-fill-normal-normal w-260 p-8">
      <ConnectorCatalog {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.queryByRole('button', { name: '연결' })).not.toBeInTheDocument();
    await expect(canvas.getAllByRole('button', { name: /연결됨/ })).toHaveLength(5);
  },
};

/**
 * 2단 배치의 우측 컬럼 — 같은 컴포넌트가 2열로 접힌다.
 * 열 수는 컨테이너 폭이 아니라 부모가 아는 정보(연동됨 목록 유무)라 prop으로 받는다.
 */
export const TwoColumn: Story = {
  args: { connectedServices: ['slack'] },
  render: (args) => (
    <div className="bg-fill-normal-normal w-195 p-8">
      <ConnectorCatalog {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연결 찾기')).toBeInTheDocument();
    await expect(canvas.getAllByRole('button', { name: /연결됨/ })).toHaveLength(1);
  },
};
