import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconMore from '@/public/icons/icon/kebab_horizontal.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbSectionHeader, { SnbBetaBadge, SnbSectionAction } from './SnbSectionHeader';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbSectionHeader',
  component: SnbSectionHeader,
  tags: ['autodocs'],
  args: { label: '프로젝트' },
  argTypes: { label: { control: 'text' }, expanded: { control: 'boolean' } },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18495-97053',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18495:97053',
      },
      viewport: { width: 320, height: 160 },
      states: [
        'default',
        'with-beta-badge',
        'long-label',
        'collapsible-expanded',
        'collapsible-collapsed',
        'one-action',
        'two-actions',
        'collapsible-with-actions',
        'collapsible-with-header-click',
        'resting-hides-affordances',
      ],
      reuseNotes: ['에이전트·즐겨찾기·최근 질문·프로젝트 네 섹션이 같은 머리글을 쓴다.'],
      layoutNotes: [
        '배지가 있으면 gap 6, 없으면 gap 2 — Figma 실측 차이다.',
        '셰브런 18, 액션 아이콘 버튼 22, 액션 사이 gap 2.',
      ],
      interactionNotes: [
        '휴지 상태에서는 셰브런도 액션도 없다 — hover·focus에서만 나온다.',
        '접기만 있으면 라벨 영역 전체가 토글 버튼이다.',
        'onClick과 접기가 함께 오면 라벨은 onClick, 셰브런은 토글로 갈라진다.',
        '액션은 라벨 버튼의 형제라 클릭이 머리글 동작으로 새지 않는다.',
      ],
    }),
  },
} satisfies Meta<typeof SnbSectionHeader>;

export default meta;

type Story = StoryObj<typeof SnbSectionHeader>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-56 flex-col p-2">{children}</div>
);

const onAdd = fn();
const onMore = fn();

/*
 * 셰브런·액션은 hover·focus에서만 나온다. userEvent.hover는 포인터 이벤트만 쏘고
 * CSS :hover를 켜지 못해서, 실제 상태인 :focus-within을 쓴다.
 */
const revealActions = (canvasElement: HTMLElement) => {
  canvasElement.querySelector<HTMLButtonElement>('[data-slot="snb-section-header"] button')!.focus();
};

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
    // 접을 수 없는 머리글은 aria-expanded를 달지 않는다 — 달면 거짓말이 된다
    await expect(canvasElement.querySelector('[aria-expanded]')).toBeNull();
    await expect(canvas.queryAllByRole('button')).toHaveLength(0);

    const shell = canvasElement.querySelector('[data-slot="snb-section-header"]');
    await expect(shell?.getBoundingClientRect().height).toBe(30);
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
    await expect(canvasElement.querySelector('[aria-expanded]')).toBeNull();
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

export const HeaderClickable: Story = {
  args: { label: '최근 질문', onClick: fn() },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const header = canvas.getByRole('button', { name: '최근 질문' });
    await expect(header).not.toHaveAttribute('aria-expanded');
    await userEvent.click(header);
    await expect(args.onClick).toHaveBeenCalledTimes(1);
  },
};

export const CollapsibleExpanded: Story = {
  args: { onToggleCollapse: fn(), expanded: true },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    // onClick이 없으면 라벨 영역 전체가 토글 버튼 하나다
    const buttons = canvas.getAllByRole('button');
    await expect(buttons).toHaveLength(1);
    await expect(buttons[0]).toHaveAttribute('aria-expanded', 'true');

    // 휴지 상태에서는 셰브런이 자리를 차지하지 않는다
    const chevron = buttons[0].querySelector('svg')!;
    await expect(chevron.getBoundingClientRect().width).toBe(0);

    revealActions(canvasElement);
    await expect(chevron.getBoundingClientRect().width).toBe(18);
    await expect(chevron.getBoundingClientRect().height).toBe(18);

    await userEvent.click(buttons[0]);
    await expect(args.onToggleCollapse).toHaveBeenCalledTimes(1);
  },
};

export const RestingHidesAffordances: Story = {
  args: {
    onToggleCollapse: fn(),
    expanded: true,
    actions: <SnbSectionAction label="프로젝트 추가" Icon={IconAdd} onClick={onAdd} />,
  },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 시안 18508:134963 — 기본 상태는 셰브런·액션이 모두 hidden이다
    await expect(canvas.queryByRole('button', { name: '프로젝트 추가' })).toBeNull();

    revealActions(canvasElement);
    await expect(canvas.getByRole('button', { name: '프로젝트 추가' })).toBeInTheDocument();

    /*
     * 시안 18508:134948 실측. 셰브런은 액션 버튼(Icon/Normal/Neutral #6d7882)보다
     * 옅은 Icon/Normal/Alternative(#b1b8be)다 — 같은 회색으로 뭉뚱그리기 쉬운 지점이다.
     */
    const header = canvasElement.querySelector('[data-slot="snb-section-header"]')!;
    const chevron = header.querySelector('button svg')!;
    await expect(getComputedStyle(chevron).color).toBe('rgb(177, 184, 190)');
    await expect(getComputedStyle(canvas.getByRole('button', { name: '프로젝트 추가' })).color).toBe(
      'rgb(109, 120, 130)',
    );
  },
};

export const CollapsibleCollapsed: Story = {
  args: { onToggleCollapse: fn(), expanded: false },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: '프로젝트' })).toHaveAttribute('aria-expanded', 'false');
  },
};

export const OneAction: Story = {
  args: {
    onClick: fn(),
    actions: <SnbSectionAction label="프로젝트 추가" Icon={IconAdd} onClick={onAdd} />,
  },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    onAdd.mockClear();
    revealActions(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: '프로젝트 추가' }));
    await expect(onAdd).toHaveBeenCalledTimes(1);
    // 액션은 라벨 버튼 바깥이라 머리글 onClick으로 새지 않는다
    await expect(args.onClick).not.toHaveBeenCalled();
  },
};

export const TwoActions: Story = {
  args: {
    onClick: fn(),
    actions: (
      <>
        <SnbSectionAction label="프로젝트 더보기" Icon={IconMore} onClick={onMore} />
        <SnbSectionAction label="프로젝트 추가" Icon={IconAdd} onClick={onAdd} />
      </>
    ),
  },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    onAdd.mockClear();
    onMore.mockClear();
    revealActions(canvasElement);

    const more = canvas.getByRole('button', { name: '프로젝트 더보기' });
    const add = canvas.getByRole('button', { name: '프로젝트 추가' });
    // 버튼 22, 사이 gap 2 — 시안 Frame 2147228940의 46px가 이 조합이다
    await expect(Math.round(more.getBoundingClientRect().width)).toBe(22);
    await expect(Math.round(add.getBoundingClientRect().left - more.getBoundingClientRect().right)).toBe(2);

    await userEvent.click(more);
    await expect(onMore).toHaveBeenCalledTimes(1);
    await expect(onAdd).not.toHaveBeenCalled();
    await expect(args.onClick).not.toHaveBeenCalled();
  },
};

export const CollapsibleWithActions: Story = {
  args: {
    onToggleCollapse: fn(),
    expanded: true,
    actions: <SnbSectionAction label="프로젝트 추가" Icon={IconAdd} onClick={onAdd} />,
  },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    onAdd.mockClear();
    revealActions(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: '프로젝트 추가' }));
    await expect(onAdd).toHaveBeenCalledTimes(1);
    await expect(args.onToggleCollapse).not.toHaveBeenCalled();
    await expect(canvas.getByRole('button', { name: '프로젝트' })).toHaveAttribute('aria-expanded', 'true');
  },
};

export const CollapsibleWithHeaderClick: Story = {
  args: {
    label: '즐겨찾기',
    onClick: fn(),
    onToggleCollapse: fn(),
    expanded: true,
    actions: <SnbSectionAction label="즐겨찾기 추가" Icon={IconAdd} onClick={onAdd} />,
  },
  render: (args) => (
    <Frame>
      <SnbSectionHeader {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    onAdd.mockClear();
    revealActions(canvasElement);

    const headerButton = canvas.getByRole('button', { name: '즐겨찾기' });
    const chevron = canvas.getByRole('button', { name: '즐겨찾기 접기' });
    // aria-expanded는 실제로 접기를 수행하는 셰브런에만 붙는다
    await expect(headerButton).not.toHaveAttribute('aria-expanded');
    await expect(chevron).toHaveAttribute('aria-expanded', 'true');

    await userEvent.click(headerButton);
    await expect(args.onClick).toHaveBeenCalledTimes(1);
    await expect(args.onToggleCollapse).not.toHaveBeenCalled();

    await userEvent.click(chevron);
    await expect(args.onToggleCollapse).toHaveBeenCalledTimes(1);
    await expect(args.onClick).toHaveBeenCalledTimes(1);
    await expect(onAdd).not.toHaveBeenCalled();
  },
};
