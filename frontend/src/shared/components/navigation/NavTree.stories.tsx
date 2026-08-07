import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import NavTree, { type NavTreeNode } from './NavTree';

/*
 * shared 스토리는 features fixture를 참조할 수 없다(ESLint boundaries) — 데이터 인라인.
 *
 * 라벨은 Figma 실측값을 옮긴 placeholder다. Figma에서는 형제 노드가 전부 똑같은
 * 문자열("채널명 text text text text…")이라 접근성 이름으로 구분이 안 되므로,
 * 스토리에서만 뒤에 번호를 붙였다. 실카피는 미정이다.
 */
const SNB_TREE: readonly NavTreeNode[] = [
  {
    id: 'channel-1',
    label: '채널명 text text text text 1',
    Icon: IconWikiChannel,
    canAddChild: true,
    children: [
      { id: 'folder-1', label: '폴더명 text text text t 1', Icon: IconFolder, canAddChild: true },
      {
        id: 'folder-2',
        label: '폴더명 text text text t 2',
        Icon: IconFolder,
        canAddChild: true,
        children: [{ id: 'file-1', label: '파일명texttexttext 1', Icon: IconFile }],
      },
    ],
  },
  { id: 'channel-2', label: '채널명 text text text text 2', Icon: IconWikiChannel, canAddChild: true },
  { id: 'channel-3', label: '채널명 text text text text 3', Icon: IconWikiChannel, canAddChild: true },
];

/** 검토 큐 우측 "문서 위치" — 채널 > 폴더 경로 조각 (Figma 17564:127054) */
const DOCUMENT_LOCATION: readonly NavTreeNode[] = [
  {
    id: 'location-channel',
    label: '채널명',
    Icon: IconWikiChannel,
    children: [{ id: 'location-folder', label: '폴더명', Icon: IconFolder }],
  },
];

const meta = {
  title: 'Compositions/Shared/Navigation/NavTree',
  component: NavTree,
  tags: ['autodocs'],
  args: { nodes: SNB_TREE },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17578-127214',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17578:127214',
      },
      viewport: { width: 280, height: 360 },
      states: ['interactive', 'active', 'static-location', 'long-label-narrow'],
      reuseNotes: [
        'SNB 프로젝트 섹션(탐색형, 17578:127214 > Projects Section 17884:15677)과 검토 큐 "문서 위치"(표시형, 17564:127054)가 같은 트리를 쓴다.',
        'onNodeClick을 안 넘기면 정적 표시로 동작한다 — 표시형이 이 모드다. 전체 펼침 고정이고 버튼이 없다.',
        '도메인 무지 컴포넌트다. 채널/폴더/문서라는 의미는 소비처가 Icon과 label로 주입한다.',
      ],
      layoutNotes: [
        '탐색형 행은 Figma SNB/menu 인스턴스와 형상이 같다(h 36, px 10, gap 12, radius 8, 아이콘 슬롯 22).',
        '들여쓰기 단위가 모드마다 다르다 — 탐색형 20px(depth x = 0/20/40), 표시형 16px(depth x = 0/16).',
        '표시형은 행 높이 28에 행 간격 8이고, depth > 0 행 앞에 arrow_right2 연결자가 붙는다.',
      ],
      dataNotes: [
        'Figma 라벨은 전부 placeholder("채널명 text text text text…", "폴더명 text text text t…", "파일명texttexttext…") — 실카피 미정.',
        'Figma 트리는 채널 1개에 폴더 2개, 두 번째 폴더 아래 파일 1개까지만 그려져 있다. depth 4 이상은 디자인 미제공.',
      ],
      tokenNotes: [
        '탐색형 아이콘은 Icon/Normal/Neutral(#6d7882 = icon-normal-neutral)이다. 같은 SNB/menu라도 Primary Nav 쪽은 Icon/Normal/Normal(#464c53)이라 값이 다르다.',
        '표시형은 항목 아이콘이 Icon/Normal/Normal, 연결자 화살표만 Icon/Normal/Neutral이다.',
        '라벨은 양쪽 다 Text/Normal/Normal + body(md)/small(15/1.5).',
      ],
      interactionNotes: [
        'Figma에 별도 펼침 화살표(caret)가 없다 — 행 자체가 토글 어포던스다.',
        'hover·pressed는 CSS 상태라 스토리로 고정하지 않는다.',
      ],
    }),
  },
} satisfies Meta<typeof NavTree>;

export default meta;

type Story = StoryObj<typeof NavTree>;

/** Figma SNB Nav Area 폭 224 = w-56. 컴포넌트는 폭을 안 가지므로 슬롯이 정한다 */
const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-56 p-2">{children}</div>
);

const left = (element: Element) => element.getBoundingClientRect().left;

/** 라벨 버튼에서 그 행의 컨테이너를 찾는다. 배경·들여쓰기·행 높이는 전부 컨테이너가 갖는다 */
const rowOf = (labelButton: Element) => labelButton.closest('[data-slot="nav-tree-row"]')!;

export const Interactive: Story = {
  args: {
    activeId: 'file-1',
    defaultExpandedIds: ['channel-1', 'folder-2'],
    onNodeClick: fn(),
  },
  render: (args) => (
    <Frame>
      <NavTree {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    const channel = canvas.getByRole('button', { name: '채널명 text text text text 1' });
    const folder = canvas.getByRole('button', { name: '폴더명 text text text t 1' });
    const file = canvas.getByRole('button', { name: '파일명texttexttext 1' });

    // depth마다 20px씩 들여쓴다 (Figma 17873:46294 — Depth 2 List x=20, Depth 3 List x=40)
    await expect(left(rowOf(folder)) - left(rowOf(channel))).toBe(20);
    await expect(left(rowOf(file)) - left(rowOf(channel))).toBe(40);
    // 들여쓴 행은 오른쪽 끝이 밀리지 않는다 — 폭이 줄어들 뿐이다
    await expect(rowOf(folder).getBoundingClientRect().right).toBe(rowOf(channel).getBoundingClientRect().right);

    // 행 본문 클릭은 이동만 한다 — 더 이상 접히지 않는다
    await userEvent.click(channel);
    await expect(args.onNodeClick).toHaveBeenCalledWith('channel-1');
    await expect(canvas.getByRole('button', { name: '파일명texttexttext 1' })).toBeInTheDocument();

    // 접기/펼치기는 캐럿만 한다. 캐럿은 hover 또는 포커스에서 나타난다
    channel.focus();
    const collapse = canvas.getByRole('button', { name: '채널명 text text text text 1 접기' });
    await expect(collapse).toHaveAttribute('aria-expanded', 'true');

    await userEvent.click(collapse);
    await expect(canvas.queryByRole('button', { name: '파일명texttexttext 1' })).toBeNull();

    const expand = canvas.getByRole('button', { name: '채널명 text text text text 1 펼치기' });
    await expect(expand).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(expand);
    await expect(canvas.getByRole('button', { name: '파일명texttexttext 1' })).toBeInTheDocument();

    // 자식이 없는 행에는 캐럿 자체가 없다 — 누를 것이 없으면 어포던스도 없다
    const leaf = canvas.getByRole('button', { name: '채널명 text text text text 2' });
    leaf.focus();
    await expect(canvas.queryByRole('button', { name: '채널명 text text text text 2 펼치기' })).toBeNull();
  },
};

export const ActiveHighlight: Story = {
  args: {
    activeId: 'folder-1',
    defaultExpandedIds: ['channel-1'],
    onNodeClick: fn(),
  },
  render: (args) => (
    <Frame>
      <NavTree {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 현재 위치는 aria-current로 노출한다 — 스크린리더가 알 수 있어야 한다
    await expect(canvas.getByRole('button', { name: '폴더명 text text text t 1' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    // 하이라이트는 한 곳뿐이다
    await expect(canvasElement.querySelectorAll('[aria-current="page"]')).toHaveLength(1);

    // 선택 상태는 primary 계열이다 (Figma 17859:133090 — Fill/Primary/Normal/Neutral)
    const active = canvas.getByRole('button', { name: '폴더명 text text text t 1' });
    await expect(rowOf(active)).toHaveClass('bg-fill-primary-normal-neutral');
    await expect(active.querySelector('span')).toHaveClass('text-text-primary-normal');
  },
};

export const StaticLocation: Story = {
  // 문서 위치 표시형: onNodeClick이 없으면 액션 핸들러를 줘도 정적 모드다 — 버튼이 0개여야 한다
  args: { nodes: DOCUMENT_LOCATION, onNodeMore: fn(), onNodeAdd: fn() },
  render: (args) => (
    <Frame>
      <NavTree {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // defaultExpandedIds 없이도 하위가 보인다
    const channel = canvas.getByText('채널명');
    const folder = canvas.getByText('폴더명');
    await expect(channel).toBeInTheDocument();
    await expect(folder).toBeInTheDocument();

    // 정적 모드는 버튼이 아니다 — 누를 것이 없으면 누를 수 있게 보이면 안 된다
    await expect(canvas.queryByRole('button')).toBeNull();

    // depth > 0 행에만 연결자 화살표가 붙는다
    await expect(canvasElement.querySelectorAll('[data-slot="nav-tree-depth-connector"]')).toHaveLength(1);

    /*
     * 라벨 x가 32 → 80으로 48 벌어진다. 들여쓰기 16 + 연결자 24 + gap 8이 그 차이다
     * (Figma 17564:127054에서 채널 라벨 x=32, 폴더 라벨 x=80).
     */
    await expect(left(folder) - left(channel)).toBe(48);
  },
};

/*
 * 트리는 깊어질수록 라벨 폭이 줄어든다. Figma도 라벨을 전부 잘라서 보여준다(…).
 * 좁은 슬롯에서 줄바꿈으로 도망가지 않고 자르는지 확인한다 — 줄바꿈이 나면 행 높이가
 * 무너져서 트리 전체 리듬이 깨진다.
 */
export const LongLabelNarrow: Story = {
  args: {
    activeId: undefined,
    defaultExpandedIds: ['channel-1', 'folder-2'],
    onNodeClick: fn(),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal w-40 p-2">
      <NavTree {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const file = canvas.getByRole('button', { name: '파일명texttexttext 1' });

    // 가장 깊은 행도 36px을 유지한다 (Figma SNB/menu 행 높이)
    await expect(Math.round(rowOf(file).getBoundingClientRect().height)).toBe(36);

    // 라벨은 잘린다 — 넘치는 폭이 실제로 있어야 truncate가 일한 것이다
    const label = file.querySelector('span');
    await expect(label).not.toBeNull();
    await expect(label!.scrollWidth).toBeGreaterThan(label!.clientWidth);

    // 슬롯 밖으로 새지 않는다
    await expect(rowOf(file).getBoundingClientRect().right).toBeLessThanOrEqual(
      canvasElement.getBoundingClientRect().right,
    );
  },
};

/*
 * 행 액션은 hover와 포커스 양쪽에서 나타난다. 플레이는 포커스로만 검증한다 —
 * userEvent.hover()는 합성 이벤트라 실제 브라우저의 CSS :hover를 켜지 못한다.
 */
export const RowActions: Story = {
  args: {
    defaultExpandedIds: ['channel-1', 'folder-2'],
    onNodeClick: fn(),
    onNodeMore: fn(),
    onNodeAdd: fn(),
  },
  render: (args) => (
    <Frame>
      <NavTree {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 아무 행도 hover·포커스 상태가 아니면 액션은 보이지 않는다
    await expect(canvas.queryByRole('button', { name: '채널명 text text text text 1 더보기' })).toBeNull();

    const channel = canvas.getByRole('button', { name: '채널명 text text text text 1' });
    channel.focus();

    const more = canvas.getByRole('button', { name: '채널명 text text text text 1 더보기' });
    const add = canvas.getByRole('button', { name: '채널명 text text text text 1 하위 추가' });

    // Figma Icon button 22×22, 그룹 gap 2 (17892:26494)
    await expect(Math.round(more.getBoundingClientRect().width)).toBe(22);
    await expect(Math.round(more.getBoundingClientRect().height)).toBe(22);
    await expect(Math.round(add.getBoundingClientRect().left - more.getBoundingClientRect().right)).toBe(2);

    // 액션이 나타나면 라벨 폭이 실제로 줄어든다 — 시안이 그린 레이아웃 시프트다
    const channelLabel = channel.querySelector('span')!;
    const widthWithActions = channelLabel.getBoundingClientRect().width;
    channel.blur();
    await waitFor(async () => {
      await expect(channelLabel.getBoundingClientRect().width).toBeGreaterThan(widthWithActions);
    });

    // 하위를 가질 수 없는 행은 ⋯만 갖는다 (Figma 하위메뉴_파일 컬럼)
    const file = canvas.getByRole('button', { name: '파일명texttexttext 1' });
    file.focus();
    await expect(canvas.getByRole('button', { name: '파일명texttexttext 1 더보기' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '파일명texttexttext 1 하위 추가' })).toBeNull();

    // 액션 클릭은 이동도 토글도 건드리지 않는다
    await userEvent.click(canvas.getByRole('button', { name: '파일명texttexttext 1 더보기' }));
    await expect(args.onNodeMore).toHaveBeenCalledWith('file-1');
    await expect(args.onNodeClick).not.toHaveBeenCalled();

    // 하위 추가는 canAddChild 행에서만 불린다
    const folder = canvas.getByRole('button', { name: '폴더명 text text text t 2' });
    folder.focus();
    await userEvent.click(canvas.getByRole('button', { name: '폴더명 text text text t 2 하위 추가' }));
    await expect(args.onNodeAdd).toHaveBeenCalledWith('folder-2');
  },
};
