import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconLink from '@/public/icons/icon/link.svg';
import IconList from '@/public/icons/icon/list.svg';
import IconStar from '@/public/icons/icon/star.svg';

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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18495-97053',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18495:97053',
      },
      viewport: { width: 320, height: 280 },
      states: ['context-menu', 'add-sub-page', 'view-options', 'no-category-label'],
      reuseNotes: [
        '시안의 Category label·Dropdown menu 항목·divider·Meta info 4종을 props 조합으로 표현한다. 조합마다 컴포넌트를 나누지 않는다.',
        '팝오버 배치·열림 상태·트리거는 소비처 몫이다. 이 컴포넌트는 마크업만 낸다.',
      ],
      dataNotes: [
        'hover는 CSS 상태라 스토리로 고정하지 않는다.',
        '로딩·빈 목록·에러 상태는 시안에 없어 만들지 않는다.',
      ],
      interactionNotes: ['항목 클릭은 onSelect만 호출한다 — 메뉴를 닫는 책임은 소비처에 있다.'],
      tokenNotes: [
        '정렬/보기 메뉴의 항목 라벨은 시안이 세 줄 모두 같은 placeholder다. 실제 정렬 옵션이 정해지기 전까지 props로만 받는다.',
        '아이콘은 소비처가 주입한다 — 시안이 조합별 아이콘을 확정하지 않아 스토리 값은 예시다.',
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
const onCopyLink = fn();
const onRename = fn();

const treeRowGroups = [
  [{ id: 'favorite', label: '즐겨찾기', Icon: IconStar, onSelect: onFavorite }],
  [
    { id: 'copy-link', label: '링크 복사', Icon: IconLink, onSelect: onCopyLink },
    { id: 'rename', label: '이름 바꾸기', Icon: IconEditPencil, onSelect: onRename },
  ],
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
    await expect(canvas.getByTestId('snb-dropdown-menu-meta')).toHaveTextContent('팀원G 최종 편집');
    await expect(canvas.getAllByRole('button')).toHaveLength(3);
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

    await expect(Math.round(box(label).top - box(menu).top)).toBe(8);
    await expect(Math.round(box(items[0]).top - box(label).bottom)).toBe(8);
    await expect(Math.round(box(items[1]).top - box(items[0]).bottom)).toBe(4);
    await expect(Math.round(box(menu).bottom - box(items[1]).bottom)).toBe(8);
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
        { id: 'rename', label: '이름 바꾸기', Icon: IconEditPencil, onSelect: fn() },
      ],
    ],
  },
  render: (args) => (
    <Frame>
      <SnbDropdownMenu {...args} />
    </Frame>
  ),
};
