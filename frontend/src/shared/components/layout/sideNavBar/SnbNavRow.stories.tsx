import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconSearch from '@/public/icons/icon/search.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbNavRow from './SnbNavRow';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbNavRow',
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
      states: ['default', 'selected', 'with-count', 'count-zero', 'disabled', 'long-label', 'with-actions'],
      reuseNotes: ['Figma SNB/menu type=Main menu에 대응한다. type=setting(SnbMenuItem)과 선택 색이 다르다.'],
      dataNotes: [
        'hover·pressed는 CSS 상태라 스토리로 고정하지 않는다.',
        '액션 변형(8/24): 즐겨찾기 케밥을 위해 라벨 버튼 + 액션의 형제 구조로 갈린다 — 행 전용 시안이 없어 NavTree 행 액션 관례(hover 노출·메뉴 열림 고정)를 따른 자작 확장이다.',
      ],
      tokenNotes: [
        'disabled는 시안에 없는 상태다 — SNB/menu는 5상태(Default·Hover·Pressed·Selected·Selected_hover)뿐이라 리포 버튼 관례(text/icon-normal-assistive)를 빌렸다. 시안 요청 진행 중.',
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

export const Disabled: Story = {
  args: { label: '즐겨찾기', disabled: true },
  render: (args) => (
    <Frame>
      <SnbNavRow {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button', { name: '즐겨찾기' });

    await expect(row).toBeDisabled();
    await userEvent.click(row);
    await expect(args.onClick).not.toHaveBeenCalled();
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

/** 행 우측 액션(케밥 등). 메뉴가 열린 상태를 흉내내 actionsOpen으로 고정 노출한다. */
export const WithActions: Story = {
  args: { label: '즐겨찾기 문서', actionsOpen: true },
  render: (args) => (
    <Frame>
      <SnbNavRow
        {...args}
        actions={
          <button type="button" aria-label="즐겨찾기 문서 추가 작업" className="size-5.5 shrink-0 rounded-full">
            ⋯
          </button>
        }
      />
    </Frame>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const label = canvas.getByRole('button', { name: '즐겨찾기 문서' });
    const action = canvas.getByRole('button', { name: '즐겨찾기 문서 추가 작업' });

    // 버튼 안 버튼이 되지 않게 라벨과 액션은 형제다.
    await expect(label.contains(action)).toBe(false);
    await expect(action).toBeVisible();

    // 액션 아이콘 색은 래퍼가 정한다 — NavTree 행 액션과 같은 neutral 상속(#6D7882)
    await expect(getComputedStyle(action).color).toBe('rgb(109, 120, 130)');

    // 액션 클릭은 행 이동을 유발하지 않는다.
    await userEvent.click(action);
    await expect(args.onClick).not.toHaveBeenCalled();

    await userEvent.click(label);
    await expect(args.onClick).toHaveBeenCalledTimes(1);
  },
};
