import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbSectionHeader, { SnbBetaBadge } from './SnbSectionHeader';

const meta = {
  title: 'Compositions/Shared/Layout/SnbSectionHeader',
  component: SnbSectionHeader,
  tags: ['autodocs'],
  args: { label: '프로젝트' },
  argTypes: { label: { control: 'text' } },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17859-129062',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17859:129062',
      },
      viewport: { width: 320, height: 160 },
      states: ['default', 'with-beta-badge', 'long-label'],
      reuseNotes: ['에이전트·즐겨찾기·최근 질문·프로젝트 네 섹션이 같은 머리글을 쓴다.'],
      layoutNotes: ['배지가 있으면 gap 6, 없으면 gap 2 — Figma 실측 차이다.'],
    }),
  },
} satisfies Meta<typeof SnbSectionHeader>;

export default meta;

type Story = StoryObj<typeof SnbSectionHeader>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-56 flex-col p-2">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('프로젝트')).toBeInTheDocument();
    await expect(canvas.queryByText('베타')).toBeNull();
  },
};

export const WithBetaBadge: Story = {
  args: { label: '에이전트', badge: <SnbBetaBadge /> },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('베타')).toBeInTheDocument();
  },
};

export const LongLabel: Story = {
  args: { label: '아주 긴 섹션 이름이 들어가는 경우 말줄임 처리를 확인하기 위한 라벨' },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
};
