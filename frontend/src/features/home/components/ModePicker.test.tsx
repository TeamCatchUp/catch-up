import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockReplace = vi.fn();
const mockUsePathname = vi.fn<() => string>();
const mockUseSearchParams = vi.fn<() => URLSearchParams>();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockUsePathname(),
  useSearchParams: () => mockUseSearchParams(),
}));

import ModePicker from './ModePicker';

beforeEach(() => {
  mockUsePathname.mockReturnValue('/');
  mockUseSearchParams.mockReturnValue(new URLSearchParams());
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('ModePicker', () => {
  it('두 모드 옵션을 모두 렌더한다', () => {
    render(<ModePicker mode="ai" />);
    expect(screen.getByRole('tab', { name: /캐치스턴트 AI/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /문서 탐색/ })).toBeInTheDocument();
  });

  it('현재 모드 옵션에 aria-selected="true"가 부여된다', () => {
    render(<ModePicker mode="docs" />);
    expect(screen.getByRole('tab', { name: /문서 탐색/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /캐치스턴트 AI/ })).toHaveAttribute('aria-selected', 'false');
  });

  it('비활성 옵션 클릭 시 router.replace로 mode 파라미터를 추가한다', async () => {
    const user = userEvent.setup();
    render(<ModePicker mode="ai" />);

    await user.click(screen.getByRole('tab', { name: /문서 탐색/ }));

    expect(mockReplace).toHaveBeenCalledWith('/?mode=docs');
  });

  it('/search의 AI 모드에서 문서 탐색 전환 시 홈 문서 탐색 진입점으로 이동한다', async () => {
    const user = userEvent.setup();
    mockUsePathname.mockReturnValue('/search');
    mockUseSearchParams.mockReturnValue(new URLSearchParams('q=검색어'));
    render(<ModePicker mode="ai" />);

    await user.click(screen.getByRole('tab', { name: /문서 탐색/ }));

    expect(mockReplace).toHaveBeenCalledWith('/?mode=docs');
  });

  it('docs → ai 전환 시 mode 파라미터를 제거한다', async () => {
    const user = userEvent.setup();
    mockUsePathname.mockReturnValue('/search');
    mockUseSearchParams.mockReturnValue(new URLSearchParams('mode=docs'));
    render(<ModePicker mode="docs" />);

    await user.click(screen.getByRole('tab', { name: /캐치스턴트 AI/ }));

    expect(mockReplace).toHaveBeenCalledWith('/search');
  });

  it('이미 선택된 모드를 다시 클릭하면 navigation을 발생시키지 않는다', async () => {
    const user = userEvent.setup();
    render(<ModePicker mode="ai" />);

    await user.click(screen.getByRole('tab', { name: /캐치스턴트 AI/ }));

    expect(mockReplace).not.toHaveBeenCalled();
  });
});
