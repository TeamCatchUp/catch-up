import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconEditSquare from '@/public/icons/icon/edit_square.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconLink from '@/public/icons/icon/link.svg';
import IconList from '@/public/icons/icon/list.svg';
import IconStar from '@/public/icons/icon/star.svg';
import IconStarOff from '@/public/icons/icon/star_off.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbDropdownMenu from './SnbDropdownMenu';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbDropdownMenu',
  component: SnbDropdownMenu,
  tags: ['autodocs'],
  args: { groups: [] },
  argTypes: {
    categoryLabel: { control: 'text' },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18486-96323',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18486:96323',
      },
      viewport: { width: 320, height: 280 },
      states: [
        'context-menu',
        'favorited-context-menu',
        'non-admin-context-menu',
        'no-meta',
        'empty-group',
        'add-sub-page',
        'view-options',
        'no-category-label',
      ],
      reuseNotes: [
        '시안의 Category label·Dropdown menu 항목·divider·Meta info 4종을 props 조합으로 표현한다. 조합마다 컴포넌트를 나누지 않는다.',
        '팝오버 배치·열림 상태·트리거는 소비처 몫이다. 이 컴포넌트는 마크업만 낸다.',
      ],
      layoutNotes: [
        '8/19 시안(18658:50796 즐겨찾기 안 됨 / 18658:50795 즐겨찾기 됨) 재실측: 껍데기 250w, radius 12, padding 8/6. 8/6 구현치와 드리프트 없음.',
        '블록 좌표는 category label y=8(h20) → 항목 y=36(h31) → divider y=75 → 그룹 y=83(31+4+31) → divider y=157 → meta y=165(h40). 블록 사이 8, 그룹 안 4.',
        'divider는 x=14 w=222 — 껍데기 padding 6에 항목 padding 8을 더한 자리다. Figma는 두께 0의 stroke라 총높이 213이지만 CSS는 테두리·구분선이 1px씩 실제 높이를 차지한다.',
        '메타 줄은 13/1.5 두 줄이라 Figma 표기가 h=40(올림)이고, 브라우저 실측은 39다. 좌우 padding은 항목과 같은 8이다.',
      ],
      dataNotes: [
        'hover는 CSS 상태라 스토리로 고정하지 않는다.',
        '로딩·빈 목록·에러 상태는 시안에 없어 만들지 않는다.',
        '하단 메타(최종 편집자·시각)에 대응하는 API 필드가 없다(백엔드 협상 B13). optional 슬롯이고 스토리 값은 시안 문구 표본이다.',
      ],
      interactionNotes: [
        '항목 클릭은 onSelect만 호출한다 — 메뉴를 닫는 책임은 소비처에 있다.',
        '즐겨찾기 라벨 토글과 관리 항목 노출 여부는 소비처가 groups로 정한다. 이 컴포넌트는 권한도 즐겨찾기 상태도 모른다.',
        '항목이 모두 빠진 묶음은 구분선도 함께 사라진다 — 비관리자 메뉴에서 divider만 남는 것을 막는다.',
      ],
      tokenNotes: [
        '정렬/보기 메뉴의 항목 라벨은 시안이 세 줄 모두 같은 placeholder다. 실제 정렬 옵션이 정해지기 전까지 props로만 받는다.',
        '아이콘은 소비처가 주입한다 — 시안이 조합별 아이콘을 확정하지 않아 스토리 값은 예시다.',
        '즐겨찾기 안 됨은 icon/star + "즐겨찾기에 추가", 즐겨찾기 됨은 icon/star_off + "즐겨찾기 해제"다.',
        '항목 라벨 body(md)/small #33363d, 카테고리 라벨 body(md)/xsmall #6d7882, 메타 body(md)/xsmall #b1b8be. 구현 토큰과 값이 일치한다.',
      ],
    }),
  },
} satisfies Meta<typeof SnbDropdownMenu>;

export default meta;

type Story = StoryObj<typeof SnbDropdownMenu>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-80 flex-col items-start p-4">{children}</div>
);

const onFavorite = fn();
const onUnfavorite = fn();
const onCopyLink = fn();
const onRename = fn();

const manageGroup = [
  { id: 'copy-link', label: '링크 복사', Icon: IconLink, onSelect: onCopyLink },
  { id: 'rename', label: '이름 바꾸기', Icon: IconEditSquare, onSelect: onRename },
];

const treeRowGroups = [
  [{ id: 'favorite', label: '즐겨찾기에 추가', Icon: IconStar, onSelect: onFavorite }],
  manageGroup,
];

/** 즐겨찾기된 노드는 아이콘과 문구가 함께 뒤집힌다 */
const favoritedRowGroups = [
  [{ id: 'unfavorite', label: '즐겨찾기 해제', Icon: IconStarOff, onSelect: onUnfavorite }],
  manageGroup,
];

const treeRowMetaLines = ['팀원G 최종 편집', '오늘 오전 12:30'];

export const ChannelContextMenu: Story = {
  args: {
    categoryLabel: '채널',
    groups: treeRowGroups,
    metaLines: treeRowMetaLines,
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const menu = canvas.getByTestId('snb-dropdown-menu');

    await expect(menu.getBoundingClientRect().width).toBe(250);
    await expect(canvas.getAllByTestId('snb-dropdown-menu-divider')).toHaveLength(2);

    // 시안 18486:96323 실측 — 껍데기 테두리·구분선은 Line/Normal/Normal(#e1e2e4)로 같은 색이다
    const rgb = (el: Element, prop: string) => getComputedStyle(el).getPropertyValue(prop);
    await expect(rgb(menu, 'border-top-color')).toBe('rgb(225, 226, 228)');
    await expect(rgb(canvas.getAllByTestId('snb-dropdown-menu-divider')[0], 'background-color')).toBe(
      'rgb(225, 226, 228)',
    );
    // 하단 메타는 라벨보다 옅다 — Text/Normal/Assistive(#b1b8be)
    await expect(rgb(canvas.getByTestId('snb-dropdown-menu-meta'), 'color')).toBe('rgb(177, 184, 190)');

    // 항목 아이콘과 라벨 사이는 10이다(항목 좌우 패딩 8과 다르다)
    const favorite = canvas.getByRole('button', { name: '즐겨찾기에 추가' });
    const icon = favorite.querySelector('svg')!;
    const text = favorite.querySelector('span')!;
    await expect(
      Math.round(text.getBoundingClientRect().left - icon.getBoundingClientRect().right),
    ).toBe(10);
    await expect(icon.getBoundingClientRect().width).toBe(20);

    // 메타는 13/1.5 두 줄이다. Figma가 h=40으로 올림해 표기해도 실측은 19.5×2다
    const meta = canvas.getByTestId('snb-dropdown-menu-meta');
    await expect(meta).toHaveTextContent('팀원G 최종 편집');
    await expect(meta).toHaveTextContent('오늘 오전 12:30');
    await expect(meta.querySelectorAll('p')).toHaveLength(2);
    await expect(getComputedStyle(meta).fontSize).toBe('13px');
    await expect(canvas.getAllByRole('button')).toHaveLength(3);

    // 시안에 없는 항목을 만들지 않는다
    await expect(canvas.queryByRole('button', { name: /삭제/ })).toBeNull();
  },
};

/** 즐겨찾기된 노드 — 첫 항목이 star_off + "즐겨찾기 해제"로 뒤집힌다 */
export const FavoritedContextMenu: Story = {
  args: {
    categoryLabel: '채널',
    groups: favoritedRowGroups,
    metaLines: treeRowMetaLines,
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByRole('button', { name: '즐겨찾기에 추가' })).toBeNull();
    const unfavorite = canvas.getByRole('button', { name: '즐겨찾기 해제' });

    // 두 상태가 같은 자산을 쓰면 문구만 바뀌고 아이콘이 그대로다 — 경로 개수로 갈린다
    await expect(unfavorite.querySelectorAll('svg path')).toHaveLength(2);
    // 아이콘 자산이 currentColor여야 토큰 클래스가 먹는다
    await expect(getComputedStyle(unfavorite.querySelector('svg path')!).fill).toBe('rgb(70, 76, 83)');

    await userEvent.click(unfavorite);
    await expect(onUnfavorite).toHaveBeenCalled();
  },
};

/** 메타를 못 받은 노드 — 하단 줄과 그 구분선이 함께 빠진다 */
export const WithoutMeta: Story = {
  args: {
    categoryLabel: '폴더',
    groups: treeRowGroups,
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByTestId('snb-dropdown-menu-meta')).toBeNull();
    // 묶음 사이 구분선만 남는다 — 메타가 없으면 두 번째 구분선도 없다
    await expect(canvas.getAllByTestId('snb-dropdown-menu-divider')).toHaveLength(1);
  },
};

/** 권한으로 묶음이 통째로 비는 경우 — 구분선만 남으면 안 된다 */
export const EmptyGroup: Story = {
  args: {
    categoryLabel: '채널',
    groups: [[{ id: 'favorite', label: '즐겨찾기에 추가', Icon: IconStar, onSelect: fn() }], []],
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getAllByRole('button')).toHaveLength(1);
    await expect(canvas.queryAllByTestId('snb-dropdown-menu-divider')).toHaveLength(0);
  },
};

export const FolderContextMenu: Story = {
  args: {
    categoryLabel: '폴더',
    groups: treeRowGroups,
    metaLines: treeRowMetaLines,
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
};

export const FileContextMenu: Story = {
  args: {
    categoryLabel: '파일',
    groups: treeRowGroups,
    metaLines: treeRowMetaLines,
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const rename = canvas.getByRole('button', { name: '이름 바꾸기' });

    await expect(rename.getBoundingClientRect().height).toBe(31);
    await userEvent.click(rename);
    await expect(onRename).toHaveBeenCalled();
  },
};

/** 관리자가 아닌 채널의 노드 — 관리 항목이 빠지고, 즐겨찾기된 노드라 라벨이 뒤집힌다 */
export const NonAdminContextMenu: Story = {
  args: {
    categoryLabel: '파일',
    groups: [
      [{ id: 'unfavorite', label: '즐겨찾기 해제', Icon: IconStarOff, onSelect: onUnfavorite }],
      [{ id: 'copy-link', label: '링크 복사', Icon: IconLink, onSelect: onCopyLink }],
    ],
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    // 관리 항목은 그 노드가 속한 채널의 관리자에게만 남는다
    await expect(canvas.queryByRole('button', { name: '이름 바꾸기' })).toBeNull();
    await expect(canvas.getAllByRole('button')).toHaveLength(2);

    // 즐겨찾기된 노드에서는 해제 라벨만 뜬다
    await expect(canvas.queryByRole('button', { name: '즐겨찾기에 추가' })).toBeNull();
    const unfavorite = canvas.getByRole('button', { name: '즐겨찾기 해제' });
    await expect(canvas.getAllByTestId('snb-dropdown-menu-divider')).toHaveLength(1);

    await userEvent.click(unfavorite);
    await expect(onUnfavorite).toHaveBeenCalled();
  },
};

export const AddSubPage: Story = {
  args: {
    categoryLabel: '하위 페이지 추가',
    groups: [
      [
        { id: 'file', label: '파일', Icon: IconFile, onSelect: fn() },
        { id: 'folder', label: '폴더', Icon: IconFolder, onSelect: fn() },
      ],
    ],
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 묶음이 하나면 구분선도 하단 정보도 만들지 않는다
    await expect(canvas.queryAllByTestId('snb-dropdown-menu-divider')).toHaveLength(0);
    await expect(canvas.queryByTestId('snb-dropdown-menu-meta')).toBeNull();

    /*
     * 총높이가 아니라 간격 분배를 고정한다 — 패딩과 라벨 간격이 서로를 상쇄해
     * 합만 맞고 배치가 틀린 상태가 실제로 나왔다.
     */
    const menu = canvas.getByTestId('snb-dropdown-menu');
    const box = (el: Element) => el.getBoundingClientRect();
    const label = canvas.getByText('하위 페이지 추가');
    const items = canvas.getAllByRole('button');

    // 시안의 1px 테두리는 inside stroke라 레이아웃을 밀지 않는다 — CSS border는 밀어서 걷어낸다
    const border = menu.clientTop;
    await expect(border).toBe(1);
    await expect(Math.round(box(label).top - box(menu).top - border)).toBe(8);
    await expect(Math.round(box(items[0]).top - box(label).bottom)).toBe(8);
    await expect(Math.round(box(items[1]).top - box(items[0]).bottom)).toBe(4);
    await expect(Math.round(box(menu).bottom - box(items[1]).bottom - border)).toBe(8);
  },
};

export const ViewOptions: Story = {
  args: {
    categoryLabel: '보기',
    // 시안 세 줄이 모두 같은 placeholder다 — 실제 정렬 옵션이 정해지기 전까지 라벨을 지어내지 않는다
    groups: [
      [
        { id: 'sort-1', label: '최근 편집 순', Icon: IconList, onSelect: fn() },
        { id: 'sort-2', label: '최근 편집 순', Icon: IconList, onSelect: fn() },
        { id: 'sort-3', label: '최근 편집 순', Icon: IconList, onSelect: fn() },
      ],
    ],
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const items = canvas.getAllByRole('button', { name: '최근 편집 순' });
    await expect(items).toHaveLength(3);

    // 그룹 안 항목끼리는 4로 붙는다 (블록 사이 8과 다르다)
    const box = (el: Element) => el.getBoundingClientRect();
    await expect(Math.round(box(items[1]).top - box(items[0]).bottom)).toBe(4);
  },
};

export const WithoutCategoryLabel: Story = {
  args: {
    groups: [
      [
        { id: 'copy-link', label: '링크 복사', Icon: IconLink, onSelect: fn() },
        { id: 'rename', label: '이름 바꾸기', Icon: IconEditSquare, onSelect: fn() },
      ],
    ],
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
};
