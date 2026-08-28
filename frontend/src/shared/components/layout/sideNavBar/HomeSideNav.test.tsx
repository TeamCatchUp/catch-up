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

const mockUser = { name: '팀원G', email: 'teamlead@catchup.com', role: 'admin' as 'admin' | 'member' };

const mockSidebarState = {
  activePanel: null as string | null,
  isSidebarOpen: true,
  lastSettingsPath: '/mypage/profile',
  setActivePanel: vi.fn(),
  setSidebarOpen: vi.fn(),
  setDocSearchOpen: vi.fn(),
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
  useUserStore: (selector: (s: { user: typeof mockUser }) => unknown) => selector({ user: mockUser }),
}));

// 실데이터·포털을 쓰는 자식은 목적지 검증 범위 밖이다
vi.mock('./SnbRecentQuestionList', () => ({ default: () => null }));
vi.mock('@/shared/components/layout/sideNavBar/modal/UserModal', () => ({ UserMenuContent: () => null }));

import HomeSideNav from './HomeSideNav';

beforeEach(() => {
  mockSidebarState.activePanel = null;
  mockSidebarState.isSidebarOpen = true;
  mockUser.role = 'admin';
  mockSearchParams.clear();
  mockUsePathname.mockReturnValue('/');
});

afterEach(() => {
  vi.clearAllMocks();
});

/*
 * 섹션 머리글 액션이 주 메뉴 행과 같은 이름을 갖는다(새 채팅). 실제 브라우저에서는
 * 머리글 쪽이 hover 전까지 숨지만 jsdom에는 Tailwind가 없어 둘 다 잡힌다.
 */
const menuRow = (name: string) =>
  screen.getAllByRole('button', { name }).find((el) => !el.closest('[data-slot="snb-section-header"]'))!;

describe('HomeSideNav 펼침', () => {
  it('구 사이드바와 같은 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(menuRow('새 채팅'));
    expect(mockPush).toHaveBeenCalledWith('/');

    await user.click(screen.getByRole('button', { name: '문의 대응' }));
    expect(mockPush).toHaveBeenCalledWith('/agent-studio');


    await user.click(screen.getByRole('button', { name: '설정' }));
    expect(mockPush).toHaveBeenCalledWith('/mypage/profile');
  });

  it('최근 채팅 목록 끝의 더 보기가 질문 히스토리 패널을 연다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(screen.getByRole('button', { name: '더 보기' }));

    expect(mockSidebarState.togglePanel).toHaveBeenCalledWith('questionsHistory');
  });

  it('최근 채팅 머리글의 접기와 액션이 배선돼 있다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    // 전체 보기는 더 보기 행과 같은 목적지다
    await user.click(screen.getByRole('button', { name: '전체 보기' }));
    expect(mockSidebarState.togglePanel).toHaveBeenCalledWith('questionsHistory');

    const header = screen.getByRole('button', { name: '최근 채팅' });
    expect(header).toHaveAttribute('aria-expanded', 'true');

    await user.click(header);
    expect(screen.getByRole('button', { name: '최근 채팅' })).toHaveAttribute('aria-expanded', 'false');
    // 접으면 목록 끝의 더 보기까지 함께 사라진다
    expect(screen.queryByRole('button', { name: '더 보기' })).toBeNull();
  });

  it('시안에 없는 정렬 메뉴를 만들지 않는다', () => {
    // 시안의 정렬 항목 세 개가 전부 같은 placeholder라 지어낼 수 없다
    render(<HomeSideNav />);

    expect(screen.queryByRole('button', { name: /정렬|보기 변경/ })).toBeNull();
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

  it('시안에 없는 즐겨찾기·프로젝트 섹션을 만들지 않는다', () => {
    render(<HomeSideNav />);

    expect(screen.queryByText('즐겨찾기')).toBeNull();
    expect(screen.queryByText('프로젝트')).toBeNull();
    // 트리가 없으므로 채널 행도 없다
    expect(screen.queryByRole('button', { name: /^채널명/ })).toBeNull();
  });

  it('현재 경로에 따라 활성 메뉴가 갈린다', () => {
    mockUsePathname.mockReturnValue('/agent-studio');
    render(<HomeSideNav />);

    expect(screen.getByRole('button', { name: '문의 대응' })).toHaveAttribute('aria-current', 'page');
    expect(menuRow('새 채팅')).not.toHaveAttribute('aria-current');
  });

  it('검색 메뉴가 문서 탐색 모달을 연다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    expect(screen.queryByRole('button', { name: '문서 탐색' })).toBeNull();
    await user.click(screen.getByRole('button', { name: '검색' }));
    expect(mockSidebarState.setDocSearchOpen).toHaveBeenCalledWith(true);
  });

  it('새 위키는 채널 만들기 온보딩으로 보낸다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(screen.getByRole('button', { name: '새 위키' }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/onboarding');
  });

  it('관리자가 아니면 새 위키를 내린다', () => {
    mockUser.role = 'member';
    render(<HomeSideNav />);

    expect(screen.getByRole('button', { name: '새 위키' })).toHaveClass('hidden');
    expect(screen.getByRole('button', { name: '설정' })).not.toHaveClass('hidden');
  });

  it('설정은 새 위키와 같은 행에 선다', () => {
    render(<HomeSideNav />);

    const settings = screen.getByRole('button', { name: '설정' });
    expect(settings.parentElement).toBe(screen.getByRole('button', { name: '새 위키' }).parentElement);
  });

  it('선택돼 있어도 스페이스 스위처는 목적지로 보낸다', async () => {
    // 채팅처럼 홈 하위 화면에 들어가 있을 때 스위처가 유일한 복귀 수단이다
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(screen.getByRole('button', { name: '홈' }));
    expect(mockPush).toHaveBeenCalledWith('/');

    await user.click(screen.getByRole('button', { name: 'LLM Wiki' }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki');
  });

  it('로고가 홈으로 가는 링크다', () => {
    render(<HomeSideNav />);

    expect(screen.getByRole('link', { name: '홈으로 이동' })).toHaveAttribute('href', '/');
  });

  it('문서 탐색 모드도 홈이라 새 채팅이 현재 위치로 남는다', () => {
    mockSearchParams.set('mode', 'docs');
    render(<HomeSideNav />);

    expect(menuRow('새 채팅')).toHaveAttribute('aria-current', 'page');
  });

  // 페이지네이션 "불러오는 중..."은 구 사이드바 동작이라 이 금지 목록에서 뺀다
  it('승인 안 된 빈 목록·에러 문구를 만들지 않는다', () => {
    const { container } = render(<HomeSideNav />);

    expect(container.textContent).not.toMatch(/없습니다|비어|다시 시도|실패/);
  });
});

describe('HomeSideNav 닫힘', () => {
  beforeEach(() => {
    mockSidebarState.isSidebarOpen = false;
  });

  it('Rail 5항목이 시안 순서대로 배치된다', () => {
    render(<HomeSideNav />);

    const labels = ['새 채팅', '검색', '요청됨', '문의 대응', '최근 채팅'];
    labels.forEach((label) => expect(screen.getByRole('button', { name: label })).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '문서 탐색' })).toBeNull();
  });

  it('Rail 항목이 펼침과 같은 목적지로 이동한다', async () => {
    const user = userEvent.setup();
    render(<HomeSideNav />);

    await user.click(screen.getByRole('button', { name: '요청됨' }));
    expect(mockPush).toHaveBeenCalledWith('/llm-wiki/review');

    await user.click(screen.getByRole('button', { name: '문의 대응' }));
    expect(mockPush).toHaveBeenCalledWith('/agent-studio');

    // 최근 채팅은 라우팅이 아니라 질문 히스토리 패널 토글이다
    await user.click(screen.getByRole('button', { name: '최근 채팅' }));
    expect(mockSidebarState.togglePanel).toHaveBeenCalledWith('questionsHistory');
  });

  it('닫힘에는 트리와 섹션 머리글이 없다', () => {
    render(<HomeSideNav />);

    expect(screen.queryByText('프로젝트')).toBeNull();
    expect(screen.queryByText('에이전트')).toBeNull();
    expect(screen.queryByRole('button', { name: '더 보기' })).toBeNull();
  });
});
