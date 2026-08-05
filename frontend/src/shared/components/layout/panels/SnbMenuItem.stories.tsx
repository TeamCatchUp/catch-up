import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import IconGroup from '@/public/icons/icon/group.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbMenuItem from './SnbMenuItem';

const meta = {
  title: 'Compositions/Shared/Layout/SnbMenuItem',
  component: SnbMenuItem,
  tags: ['autodocs'],
  args: {
    label: '멤버 관리',
    selected: false,
  },
  argTypes: {
    selected: { control: 'boolean' },
    label: { control: 'text' },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=413-2139',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '413:2139',
      },
      viewport: { width: 320, height: 240 },
      states: ['default', 'selected', 'no-icon', 'long-label'],
      reuseNotes: [
        'Figma 디자인 시스템 SNB/menu(componentSet 413:2139, type=setting)에 대응한다.',
        '설정 사이드바와 커넥터 목록이 같은 컴포넌트를 쓴다 — 두 벌로 만들면 어긋난다.',
      ],
      dataNotes: ['hover·pressed는 CSS 상태라 스토리로 고정하지 않는다.'],
      tokenNotes: ['선택 배경은 Figma #F7F7F8 = bg-fill-normal-strong. 현행 파랑 계열에서 바뀐 값이다.'],
    }),
  },
} satisfies Meta<typeof SnbMenuItem>;

export default meta;

type Story = StoryObj<typeof SnbMenuItem>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-60 flex-col p-2">{children}</div>
);

export const Playground: Story = {
  args: { Icon: IconGroup },
  render: (args) => (
    <Frame>
      <SnbMenuItem {...args} />
    </Frame>
  ),
};

export const Selected: Story = {
  args: { Icon: IconGroup, selected: true },
  render: (args) => (
    <Frame>
      <SnbMenuItem {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 선택 상태는 aria-current로 노출한다 — 스크린리더가 현재 위치를 알 수 있어야 한다
    await expect(canvas.getByRole('button', { name: '멤버 관리' })).toHaveAttribute('aria-current', 'page');
  },
};

export const NoIcon: Story = {
  args: { label: '커넥터 연결' },
  render: (args) => (
    <Frame>
      <SnbMenuItem {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole('button', { name: '커넥터 연결' });

    await expect(button).toBeInTheDocument();
    // 아이콘을 안 넘기면 자리를 만들지 않는다
    await expect(button.querySelector('svg')).toBeNull();
  },
};

export const LongLabel: Story = {
  args: {
    Icon: IconGroup,
    label: 'Confluence - 아주 긴 워크스페이스명이 들어가는 경우 잘림 처리 확인용',
  },
  render: (args) => (
    <Frame>
      <SnbMenuItem {...args} />
    </Frame>
  ),
};
