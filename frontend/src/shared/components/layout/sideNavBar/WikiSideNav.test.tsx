import { render, screen } from '@testing-library/react';
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

import WikiSideNav from './WikiSideNav';

beforeEach(() => {
  mockSidebarState.isSidebarOpen = true;
  mockUsePathname.mockReturnValue('/llm-wiki');
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('WikiSideNav 펼침', () => {
  it('위키 모드 메뉴를 렌더한다', () => {
    render(<WikiSideNav />);

    expect(screen.getByRole('button', { name: '새 채팅' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
    // 접근 이름에 배지 건수가 붙는다
    expect(screen.getByRole('button', { name: /^요청됨/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '지식 대시보드' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '즐겨찾기' })).toBeInTheDocument();
    expect(screen.getByText('프로젝트')).toBeInTheDocument();
  });

  it('검색은 목적지가 없어 눌러도 이동하지 않는다', async () => {
    const user = userEvent.setup();
    render(<WikiSideNav />);

    await user.click(screen.getByRole('button', { name: '검색' }));

    expect(mockPush).not.toHaveBeenCalled();
  });

  it('즐겨찾기는 갈 곳이 없어 비활성이다', () => {
    render(<WikiSideNav />);

    expect(screen.getByRole('button', { name: '즐겨찾기' })).toBeDisabled();
  });

  it('요청됨·지식 대시보드·홈 스위처가 각자 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    render(<WikiSideNav />);

    await user.click(screen.getByRole('button', { name: /^요청됨/ }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/review');

    await user.click(screen.getByRole('button', { name: '새 채팅' }));
    expect(mockPush).toHaveBeenCalledWith('/');

    await user.click(screen.getByRole('button', { name: '홈' }));
    expect(mockPush).toHaveBeenCalledWith('/');
  });

  it('트리 행을 누르면 채널·폴더·문서 경로로 나뉘어 이동한다', async () => {
    const user = userEvent.setup();
    render(<WikiSideNav />);

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
    render(<WikiSideNav />);

    expect(screen.getByRole('button', { name: /^요청됨/ })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '지식 대시보드' })).not.toHaveAttribute('aria-current');
  });

  it('로딩·빈 목록·에러 문구를 만들지 않는다', () => {
    // 시안이 없는 상태라 발명 금지 대상이다 (docs/state-audit/전역-snb.md §7)
    const { container } = render(<WikiSideNav />);

    expect(container.textContent).not.toMatch(/불러오는|로딩|없습니다|비어|다시 시도|실패/);
  });
});

describe('WikiSideNav 닫힘', () => {
  beforeEach(() => {
    mockSidebarState.isSidebarOpen = false;
  });

  it('Rail 3항목만 렌더하고 지식 관리는 없다', () => {
    render(<WikiSideNav />);

    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '요청됨' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '콘텐츠' })).toBeInTheDocument();
    // 시안에는 남아 있으나 제품 결정으로 삭제됐다
    expect(screen.queryByRole('button', { name: '지식 관리' })).toBeNull();
    // 닫힘에는 트리가 없다
    expect(screen.queryByText('프로젝트')).toBeNull();
  });

  it('로고 버튼을 누르면 펼쳐진다', async () => {
    const user = userEvent.setup();
    render(<WikiSideNav />);

    await user.click(screen.getByRole('button', { name: '사이드바 펼치기' }));

    expect(mockSidebarState.setSidebarOpen).toHaveBeenCalledWith(true);
  });
});
