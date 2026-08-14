import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockPush = vi.fn();
const mockUsePathname = vi.fn<() => string>();
const mockSearchParams = new Map<string, string>();

vi.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => ({ get: (key: string) => mockSearchParams.get(key) ?? null }),
}));

const mockSidebarState = {
  activePanel: null as string | null,
  isSidebarOpen: true,
  lastSettingsPath: '/mypage/profile',
  setActivePanel: vi.fn(),
  setSidebarOpen: vi.fn(),
  togglePanel: vi.fn(),
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

// 실데이터·포털을 쓰는 자식은 목적지 검증 범위 밖이다
vi.mock('./SnbRecentQuestionList', () => ({ default: () => null }));
vi.mock('@/shared/components/layout/sideNavBar/modal/UserModal', () => ({ UserMenuContent: () => null }));

import HomeSideNav from './HomeSideNav';
import { HOME_FAVORITE_ITEMS } from './snbNavFixtures';

beforeEach(() => {
  mockSidebarState.activePanel = null;
  mockSidebarState.isSidebarOpen = true;
  mockSearchParams.clear();
  mockUsePathname.mockReturnValue('/');
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('HomeSideNav 펼침', () => {
  it('구 사이드바와 같은 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(screen.getByRole('button', { name: '새 채팅' }));
    expect(mockPush).toHaveBeenCalledWith('/');

    await user.click(screen.getByRole('button', { name: '검색' }));
    expect(mockPush).toHaveBeenCalledWith('/search');

    await user.click(screen.getByRole('button', { name: '문의 대응' }));
    expect(mockPush).toHaveBeenCalledWith('/agent-studio');

    await user.click(screen.getByRole('button', { name: '설정' }));
    expect(mockPush).toHaveBeenCalledWith('/mypage/profile');
  });

  it('요청됨과 모드 스위처가 위키 쪽으로 이동한다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    // 접근 이름에 배지 건수가 붙는다
    await user.click(screen.getByRole('button', { name: /^요청됨/ }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/review');

    await user.click(screen.getByRole('button', { name: 'LLM Wiki' }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki');
  });

  it('즐겨찾기는 갈 곳이 없어 비활성이다', () => {
    render(<HomeSideNav />);

    // 트리 채널 행도 "채널명"으로 시작하므로 라벨 전체를 맞춰 고른다
    const favorites = screen.getAllByRole('button', { name: HOME_FAVORITE_ITEMS[0].label });
    expect(favorites).toHaveLength(HOME_FAVORITE_ITEMS.length);
    favorites.forEach((button) => expect(button).toBeDisabled());
  });

  it('현재 경로에 따라 활성 메뉴가 갈린다', () => {
    mockUsePathname.mockReturnValue('/search');
    render(<HomeSideNav />);

    expect(screen.getByRole('button', { name: '검색' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '새 채팅' })).not.toHaveAttribute('aria-current');
  });

  it('문서 탐색 모드에서는 새 채팅이 활성이 아니다', () => {
    mockSearchParams.set('mode', 'docs');
    render(<HomeSideNav />);

    expect(screen.getByRole('button', { name: '새 채팅' })).not.toHaveAttribute('aria-current');
  });

  it('로딩·빈 목록·에러 문구를 만들지 않는다', () => {
    const { container } = render(<HomeSideNav />);

    expect(container.textContent).not.toMatch(/불러오는|로딩|없습니다|비어|다시 시도|실패/);
  });
});

describe('HomeSideNav 닫힘', () => {
  beforeEach(() => {
    mockSidebarState.isSidebarOpen = false;
  });

  it('Rail 4항목이 구 사이드바 동선을 잇는다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(screen.getByRole('button', { name: '문서 탐색' }));
    expect(mockPush).toHaveBeenCalledWith('/?mode=docs');

    await user.click(screen.getByRole('button', { name: '문의 대응' }));
    expect(mockPush).toHaveBeenCalledWith('/agent-studio');

    // 히스토리는 라우팅이 아니라 질문 히스토리 패널 토글이다
    await user.click(screen.getByRole('button', { name: '히스토리' }));
    expect(mockSidebarState.togglePanel).toHaveBeenCalledWith('questionsHistory');
  });

  it('닫힘에는 트리와 섹션이 없다', () => {
    render(<HomeSideNav />);

    expect(screen.queryByText('프로젝트')).toBeNull();
    expect(screen.queryByText('최근 질문')).toBeNull();
  });
});
