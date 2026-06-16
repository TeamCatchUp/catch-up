import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockPush = vi.fn();
const mockUsePathname = vi.fn<() => string>();
const mockUseSearchParams = vi.fn<() => URLSearchParams>();

vi.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
  useRouter: () => ({ push: mockPush }),
  useSearchParams: () => mockUseSearchParams(),
}));

const mockSidebarState = {
  activePanel: null as string | null,
  setActivePanel: vi.fn(),
  lastSettingsPath: '/mypage/profile',
};

vi.mock('@/shared/store/sidebarStore', () => ({
  useSidebarStore: Object.assign(
    (selector?: (s: typeof mockSidebarState) => unknown) =>
      selector ? selector(mockSidebarState) : mockSidebarState,
    { getState: () => mockSidebarState },
  ),
}));

vi.mock('@/shared/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import SideNavMenu from './SideNavMenu';

beforeEach(() => {
  mockSidebarState.activePanel = null;
  mockUsePathname.mockReturnValue('/');
  mockUseSearchParams.mockReturnValue(new URLSearchParams());
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('SideNavMenu', () => {
  it('열림 상태에서 홈, 캐치스턴트 AI, 문서 탐색, 설정을 모두 렌더한다', () => {
    render(<SideNavMenu isOpen={true} />);
    expect(screen.getByRole('button', { name: /홈/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /캐치스턴트 AI/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /문서 탐색/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /설정/ })).toBeInTheDocument();
  });

  it('문서 탐색 항목에 "베타" 칩이 노출된다', () => {
    render(<SideNavMenu isOpen={true} />);
    expect(screen.getAllByText('베타').length).toBeGreaterThanOrEqual(1);
  });

  it('닫힘 상태에서는 "베타" 칩이 노출되지 않는다', () => {
    render(<SideNavMenu isOpen={false} />);
    expect(screen.queryByText('베타')).not.toBeInTheDocument();
  });

  it('URL `/` (mode 없음) → "홈"만 활성 강조', () => {
    mockUsePathname.mockReturnValue('/');
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
    render(<SideNavMenu isOpen={true} />);

    const home = screen.getByRole('button', { name: /홈/ });
    const docs = screen.getByRole('button', { name: /문서 탐색/ });
    expect(home.className).toContain('bg-fill-primary-normal-neutral');
    expect(docs.className).not.toContain('bg-fill-primary-normal-neutral');
  });

  it('URL `/?mode=docs` → "문서 탐색"만 활성 강조', () => {
    mockUsePathname.mockReturnValue('/');
    mockUseSearchParams.mockReturnValue(new URLSearchParams('mode=docs'));
    render(<SideNavMenu isOpen={true} />);

    const home = screen.getByRole('button', { name: /홈/ });
    const docs = screen.getByRole('button', { name: /문서 탐색/ });
    expect(docs.className).toContain('bg-fill-primary-normal-neutral');
    expect(home.className).not.toContain('bg-fill-primary-normal-neutral');
  });

  it('URL `/search?mode=docs` → path가 /search여도 "문서 탐색"이 활성 강조', () => {
    mockUsePathname.mockReturnValue('/search');
    mockUseSearchParams.mockReturnValue(new URLSearchParams('mode=docs'));
    render(<SideNavMenu isOpen={true} />);

    const ai = screen.getByRole('button', { name: /캐치스턴트 AI/ });
    const docs = screen.getByRole('button', { name: /문서 탐색/ });
    expect(docs.className).toContain('bg-fill-primary-normal-neutral');
    expect(ai.className).not.toContain('bg-fill-primary-normal-neutral');
  });

  it('URL `/search` → "캐치스턴트 AI"만 활성 강조', () => {
    mockUsePathname.mockReturnValue('/search');
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
    render(<SideNavMenu isOpen={true} />);

    const ai = screen.getByRole('button', { name: /캐치스턴트 AI/ });
    const home = screen.getByRole('button', { name: /홈/ });
    expect(ai.className).toContain('bg-fill-primary-normal-neutral');
    expect(home.className).not.toContain('bg-fill-primary-normal-neutral');
  });

  it('settings 패널 활성 시 "설정"이 활성 강조', () => {
    mockSidebarState.activePanel = 'settings';
    render(<SideNavMenu isOpen={true} />);

    const settings = screen.getByRole('button', { name: /설정/ });
    expect(settings.className).toContain('bg-fill-primary-normal-neutral');
  });

  it('열림 상태에서 에이전트 스튜디오 메뉴를 렌더한다', () => {
    render(<SideNavMenu isOpen={true} />);

    expect(screen.getByText('에이전트')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /에이전트 스튜디오/ })).toBeInTheDocument();
  });

  it('에이전트 스튜디오는 문서 탐색 아래, 설정 위에 렌더한다', () => {
    render(<SideNavMenu isOpen={true} />);

    const docs = screen.getByRole('button', { name: /문서 탐색/ });
    const agentStudio = screen.getByRole('button', { name: /에이전트 스튜디오/ });
    const settings = screen.getByRole('button', { name: /설정/ });

    expect(docs.compareDocumentPosition(agentStudio)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(agentStudio.compareDocumentPosition(settings)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it('닫힘 상태에서 에이전트 스튜디오 텍스트를 숨긴다', () => {
    render(<SideNavMenu isOpen={false} />);

    expect(screen.queryByText('에이전트')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '에이전트 스튜디오' })).toBeInTheDocument();
  });

  it('URL `/agent-studio/new`에서 에이전트 스튜디오를 활성 강조한다', () => {
    mockUsePathname.mockReturnValue('/agent-studio/new');
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
    render(<SideNavMenu isOpen={true} />);

    const item = screen.getByRole('button', { name: /에이전트 스튜디오/ });
    expect(item.className).toContain('bg-fill-primary-normal-neutral');
  });

  it('에이전트 스튜디오 클릭 시 `/agent-studio`로 이동한다', async () => {
    const user = userEvent.setup();
    render(<SideNavMenu isOpen={true} />);

    await user.click(screen.getByRole('button', { name: /에이전트 스튜디오/ }));

    expect(mockPush).toHaveBeenCalledWith('/agent-studio');
  });
});
