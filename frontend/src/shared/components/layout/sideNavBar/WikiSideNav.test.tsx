import type { ComponentProps, ReactElement } from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockPush = vi.fn();
const mockUsePathname = vi.fn<() => string>();

vi.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
  useRouter: () => ({ push: mockPush }),
}));

const mockSidebarState = {
  isSidebarOpen: true,
  lastSettingsPath: '/mypage/profile',
  setActivePanel: vi.fn(),
  setSidebarOpen: vi.fn(),
};

vi.mock('@/shared/store/sidebarStore', () => ({
  useSidebarStore: Object.assign(
    (selector?: (s: typeof mockSidebarState) => unknown) => (selector ? selector(mockSidebarState) : mockSidebarState),
    { getState: () => mockSidebarState },
  ),
}));

vi.mock('@/shared/store/userStore', () => ({
  useUserStore: (selector: (s: { user: { name: string; email: string } }) => unknown) =>
    selector({ user: { name: '팀원G', email: 'teamlead@catchup.com' } }),
}));

// 사용자 메뉴는 쿼리·테마 provider를 요구한다 — 목적지 검증 범위 밖이다
vi.mock('@/shared/components/layout/sideNavBar/modal/UserModal', () => ({ UserMenuContent: () => null }));

import { TooltipProvider } from '@/shared/components/ui/tooltip';

import { PROJECT_TREE_NODES, WIKI_CHANNEL_ADMINS, WIKI_FAVORITE_ITEMS } from './snbNavFixtures';
import WikiSideNav, { type WikiTreeNode } from './WikiSideNav';

// 트리 행 액션의 툴팁이 Radix Provider를 요구한다. 실제 앱은 (app) 레이아웃이 준다
const renderNav = (ui: ReactElement) => render(ui, { wrapper: TooltipProvider });

// 데이터는 전부 prop이다 — 이 파일은 시안 픽스처를 넣어 표시·이동 규칙만 본다
const renderWikiNav = (props: ComponentProps<typeof WikiSideNav> = {}) =>
  renderNav(
    <WikiSideNav
      treeNodes={PROJECT_TREE_NODES}
      favorites={WIKI_FAVORITE_ITEMS}
      channelAdmins={WIKI_CHANNEL_ADMINS}
      {...props}
    />,
  );

const CHANNEL_LABEL = '채널명 text text text text text text text text';
const FOLDER_LABEL = '폴더명 text text text text text text text';

/** 픽스처의 문서는 즐겨찾기된 것뿐이라 등록 방향을 보려면 안 된 문서가 하나 필요하다 */
const UNFAVORITED_DOC = '즐겨찾기 안 된 문서';
const DOCUMENT_TREE: readonly WikiTreeNode[] = [
  { id: 'doc-1', kind: 'document', channelId: 'channel-1', href: '/llm-wiki/doc-1', label: UNFAVORITED_DOC },
];

/** 픽스처 트리는 접힌 채로 서므로 하위 행을 보려면 캐럿을 눌러 펼친다 */
const expandRow = async (user: ReturnType<typeof userEvent.setup>, label: string, index = 0) =>
  user.click(screen.getAllByRole('button', { name: `${label} 펼치기` })[index]);

beforeEach(() => {
  mockSidebarState.isSidebarOpen = true;
  mockUsePathname.mockReturnValue('/llm-wiki');
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('WikiSideNav 펼침', () => {
  it('위키 모드 메뉴를 렌더한다', () => {
    renderWikiNav();

    expect(screen.getByRole('button', { name: '새 채팅' })).toBeInTheDocument();
    // 검색은 목적지가 없어 항목째 내렸다
    expect(screen.queryByRole('button', { name: '검색' })).toBeNull();
    // 접근 이름에 배지 건수가 붙는다
    expect(screen.getByRole('button', { name: /^요청됨/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '대시보드' })).toBeInTheDocument();
    // 즐겨찾기는 단일 행이 아니라 섹션이다 (시안 15338:92139)
    expect(screen.getByText('즐겨찾기')).toBeInTheDocument();
    expect(screen.getByText('위키')).toBeInTheDocument();
  });

  it('즐겨찾기 행은 자기 문서 경로로 이동한다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    const favorites = screen.getAllByRole('button', { name: /^채널명 text text text text text text$/ });
    expect(favorites).toHaveLength(5);

    await user.click(favorites[0]);
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/wiki-fav-1');
  });

  it('목적지가 없는 즐겨찾기 행은 비활성이다', () => {
    renderWikiNav({ favorites: [{ id: 'fav-1', label: '목적지 없는 문서' }] });

    expect(screen.getByRole('button', { name: '목적지 없는 문서' })).toBeDisabled();
  });

  it('요청됨·대시보드·홈 스위처가 각자 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    await user.click(screen.getByRole('button', { name: /^요청됨/ }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/review');

    await user.click(screen.getByRole('button', { name: '새 채팅' }));
    expect(mockPush).toHaveBeenCalledWith('/');

    await user.click(screen.getByRole('button', { name: '홈' }));
    expect(mockPush).toHaveBeenCalledWith('/');
  });

  it('트리 행을 누르면 노드가 들고 있는 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    /*
     * 라벨을 정확히 맞춘다. jsdom에는 Tailwind가 없어 `hidden`이 캐럿 버튼을 숨기지
     * 못하는데, 캐럿의 접근 이름이 "<라벨> 접기"라 접두사 매칭이면 캐럿이 먼저 잡힌다.
     * 픽스처의 채널·폴더 라벨은 서로 같아 순서로 고른다.
     */
    await user.click(screen.getAllByRole('button', { name: CHANNEL_LABEL })[0]);
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/channel/channel-1');

    await expandRow(user, CHANNEL_LABEL);
    await user.click(screen.getAllByRole('button', { name: FOLDER_LABEL })[0]);
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/folder/folder-1');

    await expandRow(user, FOLDER_LABEL);
    await user.click(screen.getByRole('button', { name: '파일명texttexttexttext' }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/file-1');
  });

  it('트리를 펼치면 그 노드 id가 밖으로 나간다', async () => {
    const user = userEvent.setup();
    const onNodeToggle = vi.fn();
    renderWikiNav({ onNodeToggle });

    await expandRow(user, CHANNEL_LABEL);
    expect(onNodeToggle).toHaveBeenCalledWith('channel-1', true);

    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 접기` })[0]);
    expect(onNodeToggle).toHaveBeenLastCalledWith('channel-1', false);
  });

  it('현재 경로가 트리 노드의 목적지면 그 행이 활성이다', () => {
    mockUsePathname.mockReturnValue('/llm-wiki/channel/channel-2');
    renderWikiNav();

    expect(screen.getAllByRole('button', { name: CHANNEL_LABEL })[1]).toHaveAttribute('aria-current', 'page');
    expect(screen.getAllByRole('button', { name: CHANNEL_LABEL })[0]).not.toHaveAttribute('aria-current');
  });

  it('현재 경로가 검토 큐면 요청됨이 활성이고 대시보드는 아니다', () => {
    mockUsePathname.mockReturnValue('/llm-wiki/review');
    renderWikiNav();

    expect(screen.getByRole('button', { name: /^요청됨/ })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '대시보드' })).not.toHaveAttribute('aria-current');
  });

  it('트리 행의 더보기를 누르면 행 종류에 맞는 메뉴가 열린다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    // 액션은 hover·포커스에서만 나온다. jsdom엔 Tailwind가 없어 항상 트리에 있지만
    // 접근 이름으로 좁혀야 캐럿이 아니라 더보기가 잡힌다
    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0]);

    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(screen.getByText('채널')).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '이름 바꾸기' })).toBeInTheDocument();
    // 즐겨찾기는 artifact 단위 API라 채널 행에는 보낼 경로가 없다
    expect(menu.queryByRole('button', { name: /즐겨찾기/ })).toBeNull();
    // 시안에 삭제 항목은 없다
    expect(screen.queryByRole('button', { name: /삭제/ })).toBeNull();
    // 노드가 메타를 들고 있으면 하단 줄이 붙는다
    expect(screen.getByTestId('snb-dropdown-menu-meta')).toHaveTextContent('팀원G 최종 편집');
    // 즐겨찾기 묶음이 비어 구분선은 메타 앞 하나만 남는다
    expect(screen.getAllByTestId('snb-dropdown-menu-divider')).toHaveLength(1);

    // 팝오버 기본 클래스의 overflow-hidden이 남으면 메뉴 그림자가 잘린다
    const popover = screen.getByTestId('snb-dropdown-menu').parentElement!;
    expect(popover).toHaveClass('overflow-visible');
    expect(popover).not.toHaveClass('overflow-hidden');
  });

  it('트리 행의 하위 추가를 누르면 폴더 항목만 열린다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 하위 페이지 추가` })[0]);

    expect(screen.getByText('하위 페이지 추가')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '폴더' })).toBeInTheDocument();
    // 문서 생성 API가 없어 파일 항목을 두지 않는다
    expect(screen.queryByRole('button', { name: '파일' })).toBeNull();
  });

  it('폴더 항목을 고르면 빈 입력이 이어 뜨고 제출이 채널 노드째 나간다', async () => {
    const user = userEvent.setup();
    const onFolderCreateSubmit = vi.fn();
    renderWikiNav({ onFolderCreateSubmit });

    const add = screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 하위 페이지 추가` })[0];
    await user.click(add);
    await user.click(screen.getByRole('button', { name: '폴더' }));

    // 이름 바꾸기와 달리 기존 값을 물려받지 않는다
    const input = screen.getByRole('textbox', { name: '폴더 이름' });
    expect(input).toHaveValue('');
    // 앵커가 사라지면 팝오버가 좌상단으로 튄다 — 입력이 떠 있는 동안 행 액션이 남아야 한다
    expect(add.parentElement).toHaveClass('flex');
    expect(add.parentElement).not.toHaveClass('hidden');

    // 앞뒤 공백은 지워 나간다 — 서버 제약이 min_length뿐이라 여기서 안 다듬으면 유사 중복 폴더가 생긴다
    await user.type(input, '  장애 대응  {Enter}');

    expect(onFolderCreateSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'channel-1', kind: 'channel' }),
      '장애 대응',
    );
    expect(screen.queryByTestId('snb-rename-popover')).toBeNull();
  });

  it('공백뿐인 폴더 이름은 제출되지 않고 입력이 남는다', async () => {
    const user = userEvent.setup();
    const onFolderCreateSubmit = vi.fn();
    renderWikiNav({ onFolderCreateSubmit });

    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 하위 페이지 추가` })[0]);
    await user.click(screen.getByRole('button', { name: '폴더' }));
    await user.type(screen.getByRole('textbox', { name: '폴더 이름' }), '   {Enter}');

    expect(onFolderCreateSubmit).not.toHaveBeenCalled();
    expect(screen.getByTestId('snb-rename-popover')).toBeInTheDocument();
  });

  // 접기는 높이 애니메이션이 끝난 뒤에 언마운트된다 — 클릭 직후에는 아직 트리에 있다
  it('섹션 머리글로 즐겨찾기·위키를 접을 수 있다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    const favoriteRows = () => screen.queryAllByRole('button', { name: /^채널명 text text text text text text$/ });
    expect(favoriteRows()).toHaveLength(5);

    const favorites = screen.getByRole('button', { name: '즐겨찾기' });
    expect(favorites).toHaveAttribute('aria-expanded', 'true');

    await user.click(favorites);
    expect(screen.getByRole('button', { name: '즐겨찾기' })).toHaveAttribute('aria-expanded', 'false');
    await waitFor(() => expect(favoriteRows()).toHaveLength(0));

    // 트리는 자기 머리글만 따른다 — 즐겨찾기를 접어도 남는다
    const treeRows = () =>
      screen.queryAllByRole('button', { name: /^채널명 text text text text text text text text$/ });
    expect(treeRows()).toHaveLength(3);
    await user.click(screen.getByRole('button', { name: '위키' }));
    await waitFor(() => expect(treeRows()).toHaveLength(0));
  });

  it('메뉴가 열린 동안 그 행의 액션이 유지된다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    /*
     * 액션이 사라지면 앵커 버튼이 display:none이 되고 getBoundingClientRect가 0×0을
     * 돌려줘 팝오버가 좌상단으로 튄다. jsdom은 Tailwind가 없어 클래스로 검사한다.
     */
    const more = screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0];
    await user.click(more);

    expect(more.parentElement).toHaveClass('flex');
    expect(more.parentElement).not.toHaveClass('hidden');
    // 누른 버튼과 그 행은 메뉴가 떠 있는 동안 강조를 유지한다
    expect(more).toHaveAttribute('aria-expanded', 'true');
    expect(more.closest('[data-slot="nav-tree-row"]')).toHaveClass('bg-fill-normal-interaction-hover');
  });

  it('위키 머리글의 + 는 채널 추가 메뉴를 연다', async () => {
    const user = userEvent.setup();
    renderWikiNav({ canCreateWiki: true });

    await user.click(screen.getByRole('button', { name: '추가하기' }));

    expect(screen.getByText('하위 페이지 추가')).toBeInTheDocument();
    // 섹션에서는 채널만 만든다 — 폴더는 채널 아래에서만 생긴다
    expect(screen.getByRole('button', { name: '채널' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '폴더' })).toBeNull();
  });

  it('채널 항목은 채널을 만드는 유일한 화면인 온보딩으로 보낸다', async () => {
    const user = userEvent.setup();
    renderWikiNav({ canCreateWiki: true });

    await user.click(screen.getByRole('button', { name: '추가하기' }));
    await user.click(screen.getByRole('button', { name: '채널' }));

    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/onboarding');
  });

  it('메뉴 항목을 고르면 노드 id와 항목 키가 밖으로 나가고 메뉴가 닫힌다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    renderWikiNav({ onMenuAction });

    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0]);
    await user.click(screen.getByRole('button', { name: '링크 복사' }));

    expect(onMenuAction).toHaveBeenCalledWith('channel-1', 'copy-link');
    expect(screen.queryByTestId('snb-dropdown-menu')).toBeNull();
  });

  it('즐겨찾기된 노드는 항목 라벨이 즐겨찾기 해제로 뒤집힌다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    renderWikiNav({ onMenuAction });

    await expandRow(user, CHANNEL_LABEL);
    await expandRow(user, FOLDER_LABEL);
    await user.click(screen.getByRole('button', { name: '파일명texttexttexttext 추가 작업' }));

    // 섹션 머리글에도 같은 이름의 버튼이 있어 메뉴 안으로 좁힌다
    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(menu.getByRole('button', { name: '즐겨찾기 해제' })).toBeInTheDocument();
    expect(menu.queryByRole('button', { name: '즐겨찾기에 추가' })).toBeNull();
    // 문서는 이름 변경 API가 없어 관리자 채널의 문서에도 항목이 나오지 않는다
    expect(menu.queryByRole('button', { name: '이름 바꾸기' })).toBeNull();

    await user.click(menu.getByRole('button', { name: '즐겨찾기 해제' }));
    expect(onMenuAction).toHaveBeenCalledWith('file-1', 'unfavorite');
  });

  it('옮기기는 문서 케밥에만 뜬다 — 이동 API가 문서 단위다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0]);
    expect(within(screen.getByTestId('snb-dropdown-menu')).queryByRole('button', { name: '옮기기' })).toBeNull();
    await user.keyboard('{Escape}');

    await expandRow(user, CHANNEL_LABEL);
    await user.click(screen.getAllByRole('button', { name: `${FOLDER_LABEL} 추가 작업` })[0]);
    expect(within(screen.getByTestId('snb-dropdown-menu')).queryByRole('button', { name: '옮기기' })).toBeNull();
    await user.keyboard('{Escape}');

    await expandRow(user, FOLDER_LABEL);
    await user.click(screen.getByRole('button', { name: '파일명texttexttexttext 추가 작업' }));
    expect(within(screen.getByTestId('snb-dropdown-menu')).getByRole('button', { name: '옮기기' })).toBeInTheDocument();
  });

  it('옮기기를 고르면 메뉴가 닫히고 노드와 눌린 앵커가 소비처로 넘어간다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    const onMoveRequest = vi.fn();
    renderWikiNav({ onMenuAction, onMoveRequest });

    await expandRow(user, CHANNEL_LABEL);
    await expandRow(user, FOLDER_LABEL);
    await user.click(screen.getByRole('button', { name: '파일명texttexttexttext 추가 작업' }));
    await user.click(screen.getByRole('button', { name: '옮기기' }));

    expect(screen.queryByTestId('snb-dropdown-menu')).toBeNull();
    expect(onMenuAction).toHaveBeenCalledWith('file-1', 'move');
    expect(onMoveRequest).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'file-1', kind: 'document' }),
      expect.any(HTMLElement),
    );
  });

  it('소비처가 옮기기 패널을 띄운 행은 액션이 남는다 — 앵커가 0×0이 되면 팝오버가 튄다', async () => {
    const user = userEvent.setup();
    renderWikiNav({ moveOpenNodeId: 'file-1' });

    await expandRow(user, CHANNEL_LABEL);
    await expandRow(user, FOLDER_LABEL);

    const more = screen.getByRole('button', { name: '파일명texttexttexttext 추가 작업' });
    expect(more.parentElement).toHaveClass('flex');
    expect(more.parentElement).not.toHaveClass('hidden');
  });

  it('즐겨찾기 안 된 문서는 등록 항목이 뜨고 그 문서 id가 밖으로 나간다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    renderWikiNav({ treeNodes: DOCUMENT_TREE, onMenuAction });

    await user.click(screen.getByRole('button', { name: `${UNFAVORITED_DOC} 추가 작업` }));

    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(menu.queryByRole('button', { name: '이름 바꾸기' })).toBeNull();

    await user.click(menu.getByRole('button', { name: '즐겨찾기에 추가' }));
    expect(onMenuAction).toHaveBeenCalledWith('doc-1', 'favorite');
  });

  it('즐겨찾기 행의 케밥은 트리에 없는 문서에서도 문서 메뉴를 연다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    renderWikiNav({
      treeNodes: [],
      favorites: [{ id: 'fav-doc-1', label: '즐겨찾기 문서', href: '/llm-wiki/fav-doc-1', channelId: 'channel-1' }],
      onMenuAction,
    });

    await user.click(screen.getByRole('button', { name: '즐겨찾기 문서 추가 작업' }));

    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(menu.getByText('파일')).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '즐겨찾기 해제' })).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '옮기기' })).toBeInTheDocument();
    // 시안의 이름 바꾸기는 문서 이름 변경 API가 없어 트리 문서 케밥과 같은 판정으로 뺀다
    expect(menu.queryByRole('button', { name: '이름 바꾸기' })).toBeNull();

    await user.click(menu.getByRole('button', { name: '즐겨찾기 해제' }));
    expect(onMenuAction).toHaveBeenCalledWith('fav-doc-1', 'unfavorite');
    expect(screen.queryByTestId('snb-dropdown-menu')).toBeNull();
  });

  it('채널이 없는 즐겨찾기 문서에는 옮기기가 뜨지 않는다 — 옮길 대상을 셀 수 없다', async () => {
    const user = userEvent.setup();
    renderWikiNav({
      treeNodes: [],
      favorites: [{ id: 'fav-doc-1', label: '미분류 즐겨찾기', href: '/llm-wiki/fav-doc-1', channelId: null }],
    });

    await user.click(screen.getByRole('button', { name: '미분류 즐겨찾기 추가 작업' }));

    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    // 나머지 문서 항목은 그대로 남는다 — 옮기기만 빠진다
    expect(menu.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '즐겨찾기 해제' })).toBeInTheDocument();
    expect(menu.queryByRole('button', { name: '옮기기' })).toBeNull();
  });

  it('즐겨찾기 케밥의 옮기기는 즐겨찾기 데이터로 지은 문서 노드를 넘긴다', async () => {
    const user = userEvent.setup();
    const onMoveRequest = vi.fn();
    renderWikiNav({
      treeNodes: [],
      favorites: [{ id: 'fav-doc-1', label: '즐겨찾기 문서', href: '/llm-wiki/fav-doc-1', channelId: 'channel-1' }],
      onMoveRequest,
    });

    await user.click(screen.getByRole('button', { name: '즐겨찾기 문서 추가 작업' }));
    await user.click(screen.getByRole('button', { name: '옮기기' }));

    expect(onMoveRequest).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'fav-doc-1', kind: 'document', channelId: 'channel-1' }),
      expect.any(HTMLElement),
    );
  });

  it('관리자가 아닌 채널의 케밥에는 링크 복사만 남고 구분선이 없다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    // 픽스처의 채널 3개는 라벨이 같다 — 세 번째가 비관리자 채널이다
    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[2]);

    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(menu.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(menu.queryByRole('button', { name: '이름 바꾸기' })).toBeNull();
    expect(menu.queryByRole('button', { name: /즐겨찾기/ })).toBeNull();

    // 남는 묶음이 하나뿐이고 메타도 없는 노드라 구분선이 전부 빠진다
    expect(menu.queryByTestId('snb-dropdown-menu-meta')).toBeNull();
    expect(menu.queryAllByTestId('snb-dropdown-menu-divider')).toHaveLength(0);
  });

  it('이름 바꾸기를 고르면 입력이 이어 뜨고 제출이 노드째 나간다', async () => {
    const user = userEvent.setup();
    const onRenameSubmit = vi.fn();
    renderWikiNav({ onRenameSubmit });

    const more = screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0];
    await user.click(more);
    await user.click(screen.getByRole('button', { name: '이름 바꾸기' }));

    // 메뉴는 닫히고 같은 앵커에 입력이 이어 뜬다
    expect(screen.queryByTestId('snb-dropdown-menu')).toBeNull();
    const input = screen.getByRole('textbox', { name: '이름 바꾸기' });
    expect(input).toHaveValue(CHANNEL_LABEL);
    // 앵커가 사라지면 팝오버가 좌상단으로 튄다 — 입력이 떠 있는 동안 행 액션이 남아야 한다
    expect(more.parentElement).toHaveClass('flex');
    expect(more.parentElement).not.toHaveClass('hidden');

    await user.clear(input);
    await user.type(input, '새 채널 이름{Enter}');

    expect(onRenameSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'channel-1', kind: 'channel' }),
      '새 채널 이름',
    );
    expect(screen.queryByTestId('snb-rename-popover')).toBeNull();
  });

  it('폴더 삭제하기는 확인 모달을 거쳐 폴더 노드째 나간다', async () => {
    const user = userEvent.setup();
    const onFolderDeleteSubmit = vi.fn();
    renderWikiNav({ onFolderDeleteSubmit });

    await expandRow(user, CHANNEL_LABEL);
    await user.click(screen.getAllByRole('button', { name: `${FOLDER_LABEL} 추가 작업` })[0]);
    await user.click(screen.getByRole('button', { name: '폴더 삭제하기' }));

    // 확인 전에는 아무것도 나가지 않는다 — 문구는 서버 계약(문서는 채널 루트로 이동)을 말한다
    expect(onFolderDeleteSubmit).not.toHaveBeenCalled();
    expect(screen.getByText('폴더를 삭제할까요?')).toBeInTheDocument();
    expect(screen.getByText('폴더만 사라지고, 안에 있던 문서는 채널 바로 아래로 옮겨집니다.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '삭제하기' }));
    expect(onFolderDeleteSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'folder-1', kind: 'folder', channelId: 'channel-1' }),
    );
    expect(screen.queryByText('폴더를 삭제할까요?')).toBeNull();
  });

  it('삭제 확인을 취소하면 나가지 않는다', async () => {
    const user = userEvent.setup();
    const onFolderDeleteSubmit = vi.fn();
    renderWikiNav({ onFolderDeleteSubmit });

    await expandRow(user, CHANNEL_LABEL);
    await user.click(screen.getAllByRole('button', { name: `${FOLDER_LABEL} 추가 작업` })[0]);
    await user.click(screen.getByRole('button', { name: '폴더 삭제하기' }));
    await user.click(screen.getByRole('button', { name: '취소' }));

    expect(onFolderDeleteSubmit).not.toHaveBeenCalled();
    expect(screen.queryByText('폴더를 삭제할까요?')).toBeNull();
  });

  it('폴더 삭제하기는 관리자 채널의 폴더 케밥에만 뜬다', async () => {
    const user = userEvent.setup();
    renderWikiNav({ channelAdmins: { 'channel-1': false, 'channel-2': false, 'channel-3': false } });

    // 채널 케밥에는 애초에 없다 — 삭제 API가 폴더뿐이다
    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0]);
    expect(within(screen.getByTestId('snb-dropdown-menu')).queryByRole('button', { name: '폴더 삭제하기' })).toBeNull();
    await user.keyboard('{Escape}');

    await expandRow(user, CHANNEL_LABEL);
    await user.click(screen.getAllByRole('button', { name: `${FOLDER_LABEL} 추가 작업` })[0]);
    expect(within(screen.getByTestId('snb-dropdown-menu')).queryByRole('button', { name: '폴더 삭제하기' })).toBeNull();
  });

  it('폴더의 이름 바꾸기는 소속 채널을 함께 들고 나간다', async () => {
    const user = userEvent.setup();
    const onRenameSubmit = vi.fn();
    renderWikiNav({ onRenameSubmit });

    await expandRow(user, CHANNEL_LABEL);
    await user.click(screen.getAllByRole('button', { name: `${FOLDER_LABEL} 추가 작업` })[0]);
    await user.click(screen.getByRole('button', { name: '이름 바꾸기' }));

    await user.clear(screen.getByRole('textbox', { name: '이름 바꾸기' }));
    await user.type(screen.getByRole('textbox', { name: '이름 바꾸기' }), '새 폴더 이름{Enter}');

    expect(onRenameSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'folder-1', kind: 'folder', channelId: 'channel-1' }),
      '새 폴더 이름',
    );
  });

  it('입력을 Escape로 닫으면 제출되지 않는다', async () => {
    const user = userEvent.setup();
    const onRenameSubmit = vi.fn();
    renderWikiNav({ onRenameSubmit });

    await user.click(screen.getAllByRole('button', { name: `${CHANNEL_LABEL} 추가 작업` })[0]);
    await user.click(screen.getByRole('button', { name: '이름 바꾸기' }));
    await user.keyboard('{Escape}');

    expect(screen.queryByTestId('snb-rename-popover')).toBeNull();
    expect(onRenameSubmit).not.toHaveBeenCalled();
  });

  it('하위 추가(+)는 관리자 채널 행에만 붙고 판정은 prop을 따른다', async () => {
    const addButtons = () => screen.queryAllByRole('button', { name: `${CHANNEL_LABEL} 하위 페이지 추가` });

    const user = userEvent.setup();
    const { unmount } = renderWikiNav();
    expect(addButtons()).toHaveLength(2);

    // 폴더 안에는 만들 것이 없다 — 폴더 행에는 + 가 붙지 않는다
    await expandRow(user, CHANNEL_LABEL);
    expect(screen.queryAllByRole('button', { name: `${FOLDER_LABEL} 하위 페이지 추가` })).toHaveLength(0);
    unmount();

    // 같은 노드라도 채널 관리자 판정이 바뀌면 어포던스가 따라 바뀐다
    renderWikiNav({ channelAdmins: { 'channel-1': false, 'channel-2': false, 'channel-3': true } });
    expect(addButtons()).toHaveLength(1);
  });

  it('새 위키·섹션 추가는 플랫폼 관리자에게만 보인다', () => {
    renderWikiNav();

    expect(screen.queryByRole('button', { name: '추가하기' })).toBeNull();
    // SnbFooter가 CSS로 감춘다. jsdom엔 Tailwind가 없어 클래스로 검사한다
    expect(screen.getByRole('button', { name: '새 위키' }).parentElement).toHaveClass('hidden');
  });

  it('플랫폼 관리자는 새 위키로 온보딩에 진입한다', async () => {
    const user = userEvent.setup();
    renderWikiNav({ canCreateWiki: true });

    const newWiki = screen.getByRole('button', { name: '새 위키' });
    expect(newWiki.parentElement).not.toHaveClass('hidden');
    expect(screen.getByRole('button', { name: '추가하기' })).toBeInTheDocument();

    await user.click(newWiki);
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/onboarding');
  });

  it('로딩·빈 목록·에러 문구를 만들지 않는다', () => {
    // 시안이 없는 상태라 발명 금지 대상이다 (docs/state-audit/전역-snb.md §7)
    const { container } = renderNav(<WikiSideNav />);

    expect(container.textContent).not.toMatch(/불러오는|로딩|없습니다|비어|다시 시도|실패/);
    // 데이터가 아직 없으면 섹션 머리글만 남는다
    expect(screen.getByText('위키')).toBeInTheDocument();
  });
});

describe('WikiSideNav 닫힘', () => {
  beforeEach(() => {
    mockSidebarState.isSidebarOpen = false;
  });

  it('Rail 항목을 시안 순서대로 렌더한다', () => {
    renderWikiNav();

    ['새 채팅', '요청됨', '대시보드'].forEach((label) =>
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument(),
    );
    // 즐겨찾기·최근 위키는 갈 곳이 없어 접힘에서 뺐다
    expect(screen.queryByRole('button', { name: '즐겨찾기' })).toBeNull();
    expect(screen.queryByRole('button', { name: '최근 위키' })).toBeNull();
    // 지식 관리는 제품 결정으로 빠졌고, 검색은 목적지가 없어 내렸다
    expect(screen.queryByRole('button', { name: '지식 관리' })).toBeNull();
    expect(screen.queryByRole('button', { name: '검색' })).toBeNull();
    // 닫힘에는 트리가 없다
    expect(screen.queryByText('위키')).toBeNull();
  });

  it('로고 버튼을 누르면 펼쳐진다', async () => {
    const user = userEvent.setup();
    renderWikiNav();

    await user.click(screen.getByRole('button', { name: '사이드바 펼치기' }));

    expect(mockSidebarState.setSidebarOpen).toHaveBeenCalledWith(true);
  });

  it('새 채팅 아이콘은 원형 배경 위에 얹힌다 — 홈 레일과 같은 만들기 구분이다', () => {
    renderWikiNav();

    const disc = screen.getByRole('button', { name: '새 채팅' }).querySelector('span > span');
    expect(disc).toHaveClass('bg-fill-normal-interaction-disable', 'rounded-full');
  });
});

describe('SNB 폭 전환', () => {
  const frame = (container: HTMLElement) =>
    container.querySelector<HTMLElement>('[data-slot="side-nav-motion-frame"]')!;

  it('열림·닫힘 폭 변수를 틀이 들고 있고 폭 전환 클래스가 걸려 있다', () => {
    mockSidebarState.isSidebarOpen = true;
    const opened = renderWikiNav();
    expect(frame(opened.container).style.width).toBe('var(--snb-width-open)');
    expect(frame(opened.container).className).toContain('transition-[width]');
    opened.unmount();

    mockSidebarState.isSidebarOpen = false;
    const collapsed = renderWikiNav();
    expect(frame(collapsed.container).style.width).toBe('var(--snb-width-collapsed)');
  });

  // 동시에 서면 nav 랜드마크가 둘이 되고 나가는 사본이 히트테스트에 남는다
  it('열림→닫힘 전환은 순차다 — 두 네비가 동시에 마운트되지 않는다', async () => {
    mockSidebarState.isSidebarOpen = true;
    const view = renderWikiNav();
    expect(frame(view.container).children).toHaveLength(1);

    mockSidebarState.isSidebarOpen = false;
    view.rerender(
      <WikiSideNav
        treeNodes={PROJECT_TREE_NODES}
        favorites={WIKI_FAVORITE_ITEMS}
        channelAdmins={WIKI_CHANNEL_ADMINS}
      />,
    );

    // 나가는 사본이 끝나기 전에는 들어오는 사본이 마운트되지 않는다
    expect(frame(view.container).children).toHaveLength(1);
    await waitFor(() => expect(screen.getByRole('button', { name: '사이드바 펼치기' })).toBeInTheDocument(), {
      timeout: 3000,
    });
    expect(frame(view.container).children).toHaveLength(1);
  });
});
