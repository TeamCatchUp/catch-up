import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconSearch from '@/public/icons/icon/search.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbRailItem from './SnbRailItem';

const meta = {
  title: 'Compositions/Shared/Layout/SnbRailItem',
  component: SnbRailItem,
  tags: ['autodocs'],
  args: { Icon: IconSearch, label: '검색', selected: false, onClick: fn() },
  argTypes: { selected: { control: 'boolean' }, hasNotification: { control: 'boolean' } },
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
      viewport: { width: 200, height: 200 },
      states: ['default', 'selected', 'with-notification', 'long-label'],
      layoutNotes: ['선택 배경은 아이콘 프레임 36×36에만 들어간다 — 라벨까지 덮지 않는다.'],
      tokenNotes: [
        '라벨 11px는 타이포 스케일에 없어 arbitrary value를 쓴다.',
        '선택 라벨은 Text/Primary/Normal, 기본은 Text/Normal/Alternative다.',
      ],
    }),
  },
} satisfies Meta<typeof SnbRailItem>;

export default meta;

type Story = StoryObj<typeof SnbRailItem>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-16 flex-col items-center p-2">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbRailItem {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const item = canvas.getByRole('button', { name: '검색' });

    await expect(item).not.toHaveAttribute('aria-current');
    await expect(canvas.queryByTestId('snb-rail-item-dot')).toBeNull();
    // 아이콘 칸이 36×36이다 (Figma type=closed menu)
    const iconSlot = item.querySelector('span');
    await expect(Math.round(iconSlot!.getBoundingClientRect().width)).toBe(36);
    await expect(Math.round(iconSlot!.getBoundingClientRect().height)).toBe(36);
  },
};

export const Selected: Story = {
  args: { label: '요청됨', selected: true },
  render: (args) => (
    <Frame>
      <SnbRailItem {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const item = canvas.getByRole('button', { name: '요청됨' });

    await expect(item).toHaveAttribute('aria-current', 'page');
    // 선택 배경은 아이콘 칸에만 들어간다 — 버튼 전체를 덮지 않는다
    await expect(item).not.toHaveClass('bg-fill-primary-normal-neutral');
    await expect(item.querySelector('span')).toHaveClass('bg-fill-primary-normal-neutral');
  },
};

export const WithNotification: Story = {
  args: { label: '요청됨', selected: true, hasNotification: true },
  render: (args) => (
    <Frame>
      <SnbRailItem {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByTestId('snb-rail-item-dot')).toBeInTheDocument();
  },
};

export const LongLabel: Story = {
  args: { label: '지식 관리 센터' },
  render: (args) => (
    <Frame>
      <SnbRailItem {...args} />
    </Frame>
  ),
};
