import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconTeamspace from '@/public/icons/icon/teamspace.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbTeamspaceCard from './SnbTeamspaceCard';

const meta = {
  title: 'Compositions/Shared/Layout/SnbTeamspaceCard',
  component: SnbTeamspaceCard,
  tags: ['autodocs'],
  args: { name: 'Acme의 지식 허브', Icon: IconTeamspace },
  argTypes: { name: { control: 'text' }, hasNotification: { control: 'boolean' } },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17859-129060',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17859:129060',
      },
      viewport: { width: 320, height: 200 },
      states: ['default', 'with-dot', 'interactive-TBD', 'long-name'],
      dataNotes: [
        '컴포넌트명이 SNB/Dropdown이지만 열림 시안도 셰브런도 없다 — 드롭다운인지 머리글인지 미정(감사 §5-3).',
        '이름 옆 점이 무엇을 알리는지도 미정이라 표시 여부만 props로 받는다.',
      ],
      interactionNotes: ['onClick 미전달 시 button이 아닌 div로 렌더한다 — 눌리는 것처럼 보이게 하지 않는다.'],
    }),
  },
} satisfies Meta<typeof SnbTeamspaceCard>;

export default meta;

type Story = StoryObj<typeof SnbTeamspaceCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-56 flex-col p-2">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbTeamspaceCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('Acme의 지식 허브')).toBeInTheDocument();
    await expect(canvas.getByText('팀스페이스')).toBeInTheDocument();
    // 동작이 미정이라 기본은 누를 수 없는 표시다
    await expect(canvas.queryByRole('button')).toBeNull();
    await expect(canvas.queryByTestId('snb-teamspace-dot')).toBeNull();
  },
};

export const WithDot: Story = {
  args: { hasNotification: true },
  render: (args) => (
    <Frame>
      <SnbTeamspaceCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByTestId('snb-teamspace-dot')).toBeInTheDocument();
  },
};

export const InteractiveTBD: Story = {
  args: { onClick: fn() },
  render: (args) => (
    <Frame>
      <SnbTeamspaceCard {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: /Acme의 지식 허브/ }));
    await expect(args.onClick).toHaveBeenCalledTimes(1);
  },
};

export const LongName: Story = {
  args: { name: '아주 긴 팀스페이스 이름이 들어가는 경우 말줄임 처리를 확인하기 위한 이름' },
  render: (args) => (
    <Frame>
      <SnbTeamspaceCard {...args} />
    </Frame>
  ),
};
