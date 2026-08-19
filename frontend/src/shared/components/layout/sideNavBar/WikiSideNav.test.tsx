import type { ReactElement } from 'react';
import { render, screen, within } from '@testing-library/react';
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
    (selector?: (s: typeof mockSidebarState) => unknown) =>
      selector ? selector(mockSidebarState) : mockSidebarState,
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

import WikiSideNav from './WikiSideNav';

// 트리 행 액션의 툴팁이 Radix Provider를 요구한다. 실제 앱은 (app) 레이아웃이 준다
const renderNav = (ui: ReactElement) => render(ui, { wrapper: TooltipProvider });

beforeEach(() => {
  mockSidebarState.isSidebarOpen = true;
  mockUsePathname.mockReturnValue('/llm-wiki');
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('WikiSideNav 펼침', () => {
  it('위키 모드 메뉴를 렌더한다', () => {
    renderNav(<WikiSideNav />);

    expect(screen.getByRole('button', { name: '새 채팅' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
    // 접근 이름에 배지 건수가 붙는다
    expect(screen.getByRole('button', { name: /^요청됨/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '위키 대시보드' })).toBeInTheDocument();
    // 즐겨찾기는 단일 행이 아니라 섹션이다 (시안 15338:92139)
    expect(screen.getByText('즐겨찾기')).toBeInTheDocument();
    expect(screen.getByText('위키')).toBeInTheDocument();
  });

  it('검색은 목적지가 없어 눌러도 이동하지 않는다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    await user.click(screen.getByRole('button', { name: '검색' }));

    expect(mockPush).not.toHaveBeenCalled();
  });

  it('즐겨찾기 섹션의 행은 목적지가 없어 전부 비활성이다', () => {
    renderNav(<WikiSideNav />);

    const favorites = screen.getAllByRole('button', { name: /^채널명/ });
    expect(favorites.length).toBeGreaterThanOrEqual(5);
    favorites.slice(0, 5).forEach((row) => expect(row).toBeDisabled());
  });

  it('요청됨·위키 대시보드·홈 스위처가 각자 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    await user.click(screen.getByRole('button', { name: /^요청됨/ }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/review');

    await user.click(screen.getByRole('button', { name: '새 채팅' }));
    expect(mockPush).toHaveBeenCalledWith('/');

    await user.click(screen.getByRole('button', { name: '홈' }));
    expect(mockPush).toHaveBeenCalledWith('/');
  });

  it('트리 행을 누르면 채널·폴더·문서 경로로 나뉘어 이동한다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    /*
     * 라벨을 정확히 맞춘다. jsdom에는 Tailwind가 없어 `hidden`이 캐럿 버튼을 숨기지
     * 못하는데, 캐럿의 접근 이름이 "<라벨> 접기"라 접두사 매칭이면 캐럿이 먼저 잡힌다.
     * 픽스처의 채널·폴더 라벨은 서로 같아 순서로 고른다.
     */
    const channelLabel = '채널명 text text text text text text text text';
    const folderLabel = '폴더명 text text text text text text text';

    await user.click(screen.getAllByRole('button', { name: channelLabel })[0]);
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/channel/channel-1');

    await user.click(screen.getAllByRole('button', { name: folderLabel })[0]);
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/folder/folder-1');

    await user.click(screen.getByRole('button', { name: '파일명texttexttexttext' }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/file-1');
  });

  it('현재 경로가 검토 큐면 요청됨이 활성이고 대시보드는 아니다', () => {
    mockUsePathname.mockReturnValue('/llm-wiki/review');
    renderNav(<WikiSideNav />);

    expect(screen.getByRole('button', { name: /^요청됨/ })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '위키 대시보드' })).not.toHaveAttribute('aria-current');
  });

  it('트리 행의 더보기를 누르면 행 종류에 맞는 메뉴가 열린다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    // 액션은 hover·포커스에서만 나온다. jsdom엔 Tailwind가 없어 항상 트리에 있지만
    // 접근 이름으로 좁혀야 캐럿이 아니라 더보기가 잡힌다
    const channelLabel = '채널명 text text text text text text text text';
    await user.click(screen.getAllByRole('button', { name: `${channelLabel} 추가 작업` })[0]);

    expect(screen.getByText('채널')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '즐겨찾기에 추가' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '이름 바꾸기' })).toBeInTheDocument();
    // 시안에 삭제 항목은 없다
    expect(screen.queryByRole('button', { name: /삭제/ })).toBeNull();
    // 노드가 메타를 들고 있으면 하단 줄이 붙는다
    expect(screen.getByTestId('snb-dropdown-menu-meta')).toHaveTextContent('팀원G 최종 편집');
    expect(screen.getAllByTestId('snb-dropdown-menu-divider')).toHaveLength(2);

    // 팝오버 기본 클래스의 overflow-hidden이 남으면 메뉴 그림자가 잘린다
    const popover = screen.getByTestId('snb-dropdown-menu').parentElement!;
    expect(popover).toHaveClass('overflow-visible');
    expect(popover).not.toHaveClass('overflow-hidden');
  });

  it('트리 행의 하위 추가를 누르면 파일·폴더 메뉴가 열린다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    const channelLabel = '채널명 text text text text text text text text';
    await user.click(screen.getAllByRole('button', { name: `${channelLabel} 하위 페이지 추가` })[0]);

    expect(screen.getByText('하위 페이지 추가')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '파일' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '폴더' })).toBeInTheDocument();
  });

  it('섹션 머리글로 즐겨찾기·위키를 접을 수 있다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    const favoriteRows = () => screen.queryAllByRole('button', { name: /^채널명 text text text text text text$/ });
    expect(favoriteRows()).toHaveLength(5);

    const favorites = screen.getByRole('button', { name: '즐겨찾기' });
    expect(favorites).toHaveAttribute('aria-expanded', 'true');

    await user.click(favorites);
    expect(screen.getByRole('button', { name: '즐겨찾기' })).toHaveAttribute('aria-expanded', 'false');
    expect(favoriteRows()).toHaveLength(0);

    // 트리는 자기 머리글만 따른다 — 즐겨찾기를 접어도 남는다
    const treeRows = () => screen.queryAllByRole('button', { name: /^채널명 text text text text text text text text$/ });
    expect(treeRows()).toHaveLength(3);
    await user.click(screen.getByRole('button', { name: '위키' }));
    expect(treeRows()).toHaveLength(0);
  });

  it('메뉴가 열린 동안 그 행의 액션이 유지된다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    /*
     * 액션이 사라지면 앵커 버튼이 display:none이 되고 getBoundingClientRect가 0×0을
     * 돌려줘 팝오버가 좌상단으로 튄다. jsdom은 Tailwind가 없어 클래스로 검사한다.
     */
    const channelLabel = '채널명 text text text text text text text text';
    const more = screen.getAllByRole('button', { name: `${channelLabel} 추가 작업` })[0];
    await user.click(more);

    expect(more.parentElement).toHaveClass('flex');
    expect(more.parentElement).not.toHaveClass('hidden');
    // 누른 버튼과 그 행은 메뉴가 떠 있는 동안 강조를 유지한다
    expect(more).toHaveAttribute('aria-expanded', 'true');
    expect(more.closest('[data-slot="nav-tree-row"]')).toHaveClass('bg-fill-normal-interaction-hover');
  });

  it('위키 머리글의 + 는 채널 추가 메뉴를 연다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav canCreateWiki />);

    await user.click(screen.getByRole('button', { name: '추가하기' }));

    expect(screen.getByText('하위 페이지 추가')).toBeInTheDocument();
    // 섹션에서는 채널만 만든다 — 파일·폴더는 채널 아래에서만 생긴다
    expect(screen.getByRole('button', { name: '채널' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '파일' })).toBeNull();
  });

  it('메뉴 항목을 고르면 노드 id와 항목 키가 밖으로 나가고 메뉴가 닫힌다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    renderNav(<WikiSideNav onMenuAction={onMenuAction} />);

    const channelLabel = '채널명 text text text text text text text text';
    await user.click(screen.getAllByRole('button', { name: `${channelLabel} 추가 작업` })[0]);
    await user.click(screen.getByRole('button', { name: '링크 복사' }));

    expect(onMenuAction).toHaveBeenCalledWith('channel-1', 'copy-link');
    expect(screen.queryByTestId('snb-dropdown-menu')).toBeNull();
  });

  it('즐겨찾기된 노드는 항목 라벨이 즐겨찾기 해제로 뒤집힌다', async () => {
    const user = userEvent.setup();
    const onMenuAction = vi.fn();
    renderNav(<WikiSideNav onMenuAction={onMenuAction} />);

    await user.click(screen.getByRole('button', { name: '파일명texttexttexttext 추가 작업' }));

    // 섹션 머리글에도 같은 이름의 버튼이 있어 메뉴 안으로 좁힌다
    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(menu.getByRole('button', { name: '즐겨찾기 해제' })).toBeInTheDocument();
    expect(menu.queryByRole('button', { name: '즐겨찾기에 추가' })).toBeNull();

    await user.click(menu.getByRole('button', { name: '즐겨찾기 해제' }));
    expect(onMenuAction).toHaveBeenCalledWith('file-1', 'unfavorite');
  });

  it('관리자가 아닌 채널의 케밥에는 즐겨찾기·링크 복사만 남고 구분선도 하나다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    // 픽스처의 채널 3개는 라벨이 같다 — 세 번째가 비관리자 채널이다
    const channelLabel = '채널명 text text text text text text text text';
    await user.click(screen.getAllByRole('button', { name: `${channelLabel} 추가 작업` })[2]);

    const menu = within(screen.getByTestId('snb-dropdown-menu'));
    expect(menu.getByRole('button', { name: '즐겨찾기에 추가' })).toBeInTheDocument();
    expect(menu.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    expect(menu.queryByRole('button', { name: '이름 바꾸기' })).toBeNull();

    // 메타가 없는 노드라 하단 줄과 그 구분선이 함께 빠진다
    expect(menu.queryByTestId('snb-dropdown-menu-meta')).toBeNull();
    expect(menu.getAllByTestId('snb-dropdown-menu-divider')).toHaveLength(1);
  });

  it('하위 추가(+)는 관리자 채널 행에만 붙고 판정은 prop을 따른다', () => {
    const channelLabel = '채널명 text text text text text text text text';
    const addButtons = () => screen.queryAllByRole('button', { name: `${channelLabel} 하위 페이지 추가` });

    const { unmount } = renderNav(<WikiSideNav />);
    expect(addButtons()).toHaveLength(2);
    unmount();

    // 같은 노드라도 채널 관리자 판정이 바뀌면 어포던스가 따라 바뀐다
    renderNav(<WikiSideNav channelAdmins={{ 'channel-1': false, 'channel-2': false, 'channel-3': true }} />);
    expect(addButtons()).toHaveLength(1);
  });

  it('새 위키·섹션 추가는 플랫폼 관리자에게만 보인다', () => {
    renderNav(<WikiSideNav />);

    expect(screen.queryByRole('button', { name: '추가하기' })).toBeNull();
    // SnbFooter가 CSS로 감춘다. jsdom엔 Tailwind가 없어 클래스로 검사한다
    expect(screen.getByRole('button', { name: '새 위키' }).parentElement).toHaveClass('hidden');
  });

  it('플랫폼 관리자는 새 위키로 온보딩에 진입한다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav canCreateWiki />);

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
  });
});

describe('WikiSideNav 닫힘', () => {
  beforeEach(() => {
    mockSidebarState.isSidebarOpen = false;
  });

  it('Rail 6항목을 시안 순서대로 렌더한다', () => {
    renderNav(<WikiSideNav />);

    // 시안 15346:97297 — 새 채팅·검색·요청됨·위키 대시보드·즐겨찾기·최근 위키
    ['새 채팅', '검색', '요청됨', '위키 대시보드', '즐겨찾기', '최근 위키'].forEach((label) =>
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument(),
    );
    // 지식 관리는 제품 결정으로 빠졌다
    expect(screen.queryByRole('button', { name: '지식 관리' })).toBeNull();
    // 닫힘에는 트리가 없다
    expect(screen.queryByText('위키')).toBeNull();
  });

  it('로고 버튼을 누르면 펼쳐진다', async () => {
    const user = userEvent.setup();
    renderNav(<WikiSideNav />);

    await user.click(screen.getByRole('button', { name: '사이드바 펼치기' }));

    expect(mockSidebarState.setSidebarOpen).toHaveBeenCalledWith(true);
  });
});
