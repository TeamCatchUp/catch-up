import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockUsePathname = vi.fn<() => string>();

vi.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
}));

const mockSidebarState = {
  isDocSearchOpen: false,
  setSidebarOpen: vi.fn(),
  setDocSearchOpen: vi.fn(),
};

vi.mock('@/shared/store/sidebarStore', () => ({
  useSidebarStore: Object.assign(
    (selector?: (s: typeof mockSidebarState) => unknown) =>
      selector ? selector(mockSidebarState) : mockSidebarState,
    { getState: () => mockSidebarState },
  ),
}));

vi.mock('./HomeSideNav', () => ({ default: () => <div>home-snb</div> }));
vi.mock('./WikiSideNav', () => ({ default: () => <div>wiki-snb</div> }));
vi.mock('@/shared/components/search/DocSearchModal', () => ({
  default: ({ open }: { open: boolean }) => (open ? <div>doc-search-modal</div> : null),
}));

import AppSideNav, { isWikiRoute } from './AppSideNav';

beforeEach(() => {
  mockUsePathname.mockReturnValue('/');
  mockSidebarState.isDocSearchOpen = false;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('isWikiRoute', () => {
  it.each([
    ['/llm-wiki', true],
    ['/llm-wiki/review', true],
    ['/llm-wiki/channel/channel-1', true],
    ['/', false],
    // 접두사만 같은 경로는 위키가 아니다
    ['/llm-wiki-other', false],
  ])('%s → %s', (pathname, expected) => {
    expect(isWikiRoute(pathname)).toBe(expected);
  });
});

describe('AppSideNav', () => {
  it('SNB가 내려갈 때 문서 탐색 모달 열림 상태를 남기지 않는다', () => {
    mockSidebarState.isDocSearchOpen = true;
    const { unmount } = render(<AppSideNav />);
    expect(screen.getByText('doc-search-modal')).toBeInTheDocument();

    // 설정 경로는 레이아웃이 SNB째 내리므로, 남겨두면 복귀할 때 모달이 한 번 깜빡인다
    unmount();
    expect(mockSidebarState.setDocSearchOpen).toHaveBeenCalledWith(false);
  });

  it('위키 경로에서는 위키 SNB를, 그 외에는 홈 SNB를 렌더한다', () => {
    const { unmount } = render(<AppSideNav />);
    expect(screen.getByText('home-snb')).toBeInTheDocument();
    unmount();

    mockUsePathname.mockReturnValue('/llm-wiki/review');
    render(<AppSideNav />);
    expect(screen.getByText('wiki-snb')).toBeInTheDocument();
  });

  it.each([
    ['/chat/abc', false],
    ['/agent-studio/new', false],
    ['/', true],
    ['/agent-studio', true],
    ['/llm-wiki', true],
  ])('%s 진입 시 사이드바 열림은 %s다', (pathname, expected) => {
    mockUsePathname.mockReturnValue(pathname);
    render(<AppSideNav />);

    expect(mockSidebarState.setSidebarOpen).toHaveBeenCalledWith(expected);
  });
});
