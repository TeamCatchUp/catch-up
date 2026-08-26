import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let searchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => searchParams,
}));

vi.mock('@/shared/hooks/query/useQuestionHistoryGate', () => ({
  useQuestionHistoryGate: () => ({ shouldShowNoHistoryBox: false, isLoading: false }),
}));

vi.mock('@/shared/components/layout/topNavbar/TopNavbar', () => ({
  default: ({ pageType }: { pageType: string }) => <div data-testid="top-navbar">{pageType}</div>,
}));

vi.mock('./ModePicker', () => ({
  default: ({ mode }: { mode: string }) => <div data-testid="mode-picker">{mode}</div>,
}));

vi.mock('./HomeDocsSection', () => ({ default: () => <div data-testid="docs-section" /> }));
vi.mock('./AdminGuideModal', () => ({ default: () => null }));
vi.mock('./UserGuideModal', () => ({ default: () => null }));
vi.mock('./FeatureUpdateNoticeModal', () => ({ default: () => null }));

vi.mock('./HomeAiSection', () => ({
  default: ({ input }: { input: { value: string; setValue: (next: string) => void } }) => (
    <div>
      <span data-testid="composer-value">{input.value}</span>
      <button type="button" onClick={() => input.setValue('사용자가 고친 값')}>
        입력 편집
      </button>
    </div>
  ),
}));

import HomeContent from './HomeContent';

beforeEach(() => {
  searchParams = new URLSearchParams();
});

afterEach(() => {
  localStorage.clear();
});

describe('HomeContent', () => {
  it('ai 모드는 마운트 시 q 파라미터를 컴포저 초기값으로 받는다', () => {
    searchParams = new URLSearchParams('q=배포 롤백');

    render(<HomeContent />);

    expect(screen.getByTestId('composer-value')).toHaveTextContent('배포 롤백');
  });

  it('홈에 머문 채 q가 바뀌면 컴포저 입력을 새 q로 갱신한다', () => {
    searchParams = new URLSearchParams('q=첫 질문');
    const { rerender } = render(<HomeContent />);

    searchParams = new URLSearchParams('q=두 번째 질문');
    rerender(<HomeContent />);

    expect(screen.getByTestId('composer-value')).toHaveTextContent('두 번째 질문');
  });

  it('q가 사라져도 사용자가 편집한 입력을 덮어쓰지 않는다', async () => {
    searchParams = new URLSearchParams('q=첫 질문');
    const user = userEvent.setup();
    const { rerender } = render(<HomeContent />);

    await user.click(screen.getByRole('button', { name: '입력 편집' }));

    searchParams = new URLSearchParams();
    rerender(<HomeContent />);

    expect(screen.getByTestId('composer-value')).toHaveTextContent('사용자가 고친 값');
  });

  it('q가 그대로면 리렌더가 사용자의 편집을 되돌리지 않는다', async () => {
    searchParams = new URLSearchParams('q=첫 질문');
    const user = userEvent.setup();
    const { rerender } = render(<HomeContent />);

    await user.click(screen.getByRole('button', { name: '입력 편집' }));
    rerender(<HomeContent />);

    expect(screen.getByTestId('composer-value')).toHaveTextContent('사용자가 고친 값');
  });

  it('docs 모드에서는 q를 컴포저 입력으로 반영하지 않는다', () => {
    searchParams = new URLSearchParams('mode=docs&q=배포 롤백');

    render(<HomeContent />);

    expect(screen.getByTestId('docs-section')).toBeInTheDocument();
    expect(screen.queryByTestId('composer-value')).not.toBeInTheDocument();
  });

  it('mode에 따라 TopNavbar pageType이 home/docs로만 갈린다', () => {
    const { unmount } = render(<HomeContent />);
    expect(screen.getByTestId('top-navbar')).toHaveTextContent('home');
    unmount();

    searchParams = new URLSearchParams('mode=docs');
    render(<HomeContent />);
    expect(screen.getByTestId('top-navbar')).toHaveTextContent('docs');
  });
});
