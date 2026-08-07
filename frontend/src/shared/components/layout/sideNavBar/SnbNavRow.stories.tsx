import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconSearch from '@/public/icons/icon/search.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbNavRow from './SnbNavRow';

const meta = {
  title: 'Compositions/Shared/Layout/SnbNavRow',
  component: SnbNavRow,
  tags: ['autodocs'],
  args: { label: '검색', Icon: IconSearch, selected: false, onClick: fn() },
  argTypes: {
    selected: { control: 'boolean' },
    label: { control: 'text' },
    count: { control: 'number' },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17895-46181',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17895:46181',
      },
      viewport: { width: 320, height: 200 },
      states: ['default', 'selected', 'with-count', 'count-zero', 'long-label'],
      reuseNotes: ['Figma SNB/menu type=Main menu에 대응한다. type=setting(SnbMenuItem)과 선택 색이 다르다.'],
      dataNotes: ['hover·pressed는 CSS 상태라 스토리로 고정하지 않는다.'],
      tokenNotes: [
        'Selected는 fill-primary-normal-neutral(#EAF2FE)로 Figma와 정확히 일치한다.',
        '중립 hover/pressed는 solid 토큰을 쓴다 — Figma 알파 전환은 디자인 시스템 차원 별도 작업.',
      ],
    }),
  },
} satisfies Meta<typeof SnbNavRow>;

export default meta;

type Story = StoryObj<typeof SnbNavRow>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-56 flex-col p-2">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbNavRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button', { name: '검색' });

    await expect(row).not.toHaveAttribute('aria-current');
    // count를 안 넘기면 배지 DOM 자체를 만들지 않는다 — 0을 그리는 것은 발명이다
    await expect(canvas.queryByTestId('snb-nav-row-count')).toBeNull();
  },
};

export const Selected: Story = {
  args: { label: '요청됨', selected: true },
  render: (args) => (
    <Frame>
      <SnbNavRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: '요청됨' })).toHaveAttribute('aria-current', 'page');
  },
};

export const WithCount: Story = {
  args: { label: '요청됨', selected: true, count: 1 },
  render: (args) => (
    <Frame>
      <SnbNavRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByTestId('snb-nav-row-count')).toHaveTextContent('1');
  },
};

export const CountZero: Story = {
  args: { label: '요청됨', count: 0 },
  render: (args) => (
    <Frame>
      <SnbNavRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 0건 시 배지를 감출지 0을 쓸지는 미결이다 — 컴포넌트는 받은 값을 그대로 낸다
    await expect(canvas.getByTestId('snb-nav-row-count')).toHaveTextContent('0');
  },
};

export const LongLabel: Story = {
  args: { label: '아주 긴 메뉴 이름이 들어가는 경우 말줄임 처리를 확인하기 위한 라벨' },
  render: (args) => (
    <Frame>
      <SnbNavRow {...args} />
    </Frame>
  ),
};
