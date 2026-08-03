import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddedResourceTable from './EmbeddedResourceTable';

const ROWS = Array.from({ length: 4 }, (_, i) => ({
  id: `row-${i}`,
  name: `채널명 text text text text text text text text text ${i}`,
  dataRange: '2000.00.00 - 2000.00.00',
}));

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/EmbeddedResourceTable',
  component: EmbeddedResourceTable,
  tags: ['autodocs'],
  args: { service: 'slack', label: '임베딩된 채널', rows: ROWS },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17071-111748',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17071:111748',
      },
      viewport: { width: 716, height: 400 },
      states: ['rows', 'empty', 'long-name'],
      layoutNotes: ['헤더 716×36, 행 716×46, 대상 x12 w496, 범위 x524 w180.'],
      dataNotes: ['Figma는 9행 고정이고 페이지네이션이 없다 — 현행 Pagination 유지 여부는 계획 ④에서 정한다.'],
    }),
  },
} satisfies Meta<typeof EmbeddedResourceTable>;

export default meta;

type Story = StoryObj<typeof EmbeddedResourceTable>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Rows: Story = {
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('임베딩된 채널')).toBeInTheDocument();
    await expect(canvas.getByText('데이터 범위')).toBeInTheDocument();
    await expect(canvas.getAllByRole('row')).toHaveLength(5); // 헤더 1 + 본문 4
  },
};

export const Empty: Story = {
  args: { rows: [] },
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 표 대신 빈 상태로 통째로 교체된다
    await expect(canvas.getByText('임베딩한 채널이 없습니다')).toBeInTheDocument();
    await expect(canvas.queryByRole('table')).not.toBeInTheDocument();
  },
};

export const LongName: Story = {
  args: {
    service: 'confluence',
    label: '임베딩된 스페이스',
    rows: [{ id: 'x', name: '아주 긴 스페이스 이름이 들어가는 경우의 말줄임 확인용 텍스트입니다', dataRange: '-' }],
  },
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
};
