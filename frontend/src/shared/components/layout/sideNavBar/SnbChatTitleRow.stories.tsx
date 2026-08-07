import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbChatTitleRow from './SnbChatTitleRow';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbChatTitleRow',
  component: SnbChatTitleRow,
  tags: ['autodocs'],
  args: { label: '연동 테스트 중단 리스크', selected: false, onClick: fn() },
  argTypes: { selected: { control: 'boolean' }, label: { control: 'text' } },
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
      viewport: { width: 320, height: 200 },
      states: ['default', 'selected', 'with-more', 'long-label'],
      reuseNotes: ['Figma SNB/menu type=Chat Title. 아이콘 슬롯이 없고 gap이 4다(주 메뉴는 12).'],
      interactionNotes: [
        '더보기 버튼은 hover와 focus-within에서만 나타난다 — 키보드로도 도달할 수 있어야 한다.',
        'hover는 플레이로 어서션하지 않는다 — userEvent.hover()는 합성 이벤트라 브라우저의 :hover를 켜지 못한다. focus로 검증한다.',
      ],
      dataNotes: ['더보기 메뉴 항목은 미정이라 핸들러만 받는다.'],
    }),
  },
} satisfies Meta<typeof SnbChatTitleRow>;

export default meta;

type Story = StoryObj<typeof SnbChatTitleRow>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-56 flex-col p-2">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbChatTitleRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // onMoreClick 미전달 시 더보기 버튼을 만들지 않는다
    await expect(canvas.queryByRole('button', { name: /더보기/ })).toBeNull();
  },
};

export const Selected: Story = {
  args: { selected: true },
  render: (args) => (
    <Frame>
      <SnbChatTitleRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: '연동 테스트 중단 리스크' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  },
};

export const WithMore: Story = {
  args: { onMoreClick: fn() },
  render: (args) => (
    <Frame>
      <SnbChatTitleRow {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    // hover·포커스 전에는 액션이 보이지 않는다
    await expect(canvas.queryByRole('button', { name: '연동 테스트 중단 리스크 더보기' })).toBeNull();

    canvas.getByRole('button', { name: '연동 테스트 중단 리스크' }).focus();
    const more = canvas.getByRole('button', { name: '연동 테스트 중단 리스크 더보기' });

    await userEvent.click(more);
    await expect(args.onMoreClick).toHaveBeenCalledTimes(1);
    // 행 클릭과 더보기 클릭이 섞이면 안 된다
    await expect(args.onClick).not.toHaveBeenCalled();
  },
};

export const LongLabel: Story = {
  args: {
    label: '연동 테스트 중단 리스크 연동 테스트 중단 리스크 연동 테스트 중단 리스크',
    onMoreClick: fn(),
  },
  render: (args) => (
    <Frame>
      <SnbChatTitleRow {...args} />
    </Frame>
  ),
};
