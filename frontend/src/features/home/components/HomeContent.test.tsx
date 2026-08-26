import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

let searchParams = new URLSearchParams();
const push = vi.fn();
const replace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => '/',
  useSearchParams: () => searchParams,
}));

vi.mock('@/shared/components/layout/topNavbar/TopNavbar', () => ({
  default: ({ pageType }: { pageType: string }) => <div data-testid="top-navbar">{pageType}</div>,
}));

vi.mock('./DocsSearchHistorySection', () => ({ default: () => <div data-testid="docs-history" /> }));
vi.mock('./QuickTemplateList', () => ({ default: () => <div data-testid="template-list" /> }));
vi.mock('./AdminGuideModal', () => ({ default: () => null }));
vi.mock('./UserGuideModal', () => ({ default: () => null }));
vi.mock('./FeatureUpdateNoticeModal', () => ({ default: () => null }));

vi.mock('./HomeComposer', () => ({
  default: ({
    mode,
    input,
    onModeChange,
    onDocsSubmit,
  }: {
    mode: string;
    input: { value: string; setValue: (next: string) => void };
    onModeChange: (next: string) => void;
    onDocsSubmit: () => void;
  }) => (
    <div data-testid="composer" data-mode={mode}>
      <span data-testid="composer-value">{input.value}</span>
      <button type="button" onClick={() => input.setValue('사용자가 고친 값')}>
        입력 편집
      </button>
      <button type="button" onClick={() => input.setValue('지난주 결제 롤백')}>
        질의 입력
      </button>
      <button type="button" onClick={() => onModeChange('docs')}>
        문서 탐색으로
      </button>
      <button type="button" onClick={onDocsSubmit}>
        문서 검색
      </button>
    </div>
  ),
}));

import HomeContent from './HomeContent';

beforeEach(() => {
  searchParams = new URLSearchParams();
  push.mockClear();
  replace.mockClear();
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

    expect(screen.getByTestId('composer-value')).toHaveTextContent('');
  });

  it('ai 모드는 템플릿 목록을, docs 모드는 검색 기록을 아래에 둔다', () => {
    const { unmount } = render(<HomeContent />);
    expect(screen.getByTestId('template-list')).toBeInTheDocument();
    expect(screen.queryByTestId('docs-history')).not.toBeInTheDocument();
    unmount();

    searchParams = new URLSearchParams('mode=docs');
    render(<HomeContent />);
    expect(screen.getByTestId('docs-history')).toBeInTheDocument();
    expect(screen.queryByTestId('template-list')).not.toBeInTheDocument();
  });

  it('mode에 따라 TopNavbar pageType이 home/docs로만 갈린다', () => {
    const { unmount } = render(<HomeContent />);
    expect(screen.getByTestId('top-navbar')).toHaveTextContent('home');
    unmount();

    searchParams = new URLSearchParams('mode=docs');
    render(<HomeContent />);
    expect(screen.getByTestId('top-navbar')).toHaveTextContent('docs');
  });

  it('컴포저의 모드 전환은 q 같은 다른 파라미터를 남긴 채 mode만 붙인다', async () => {
    searchParams = new URLSearchParams('q=배포 롤백');
    const user = userEvent.setup();
    render(<HomeContent />);

    await user.click(screen.getByRole('button', { name: '문서 탐색으로' }));

    expect(replace).toHaveBeenCalledWith('/?q=%EB%B0%B0%ED%8F%AC+%EB%A1%A4%EB%B0%B1&mode=docs');
  });

  it('docs submit은 현재 필터를 실어 결과 페이지로 보낸다', async () => {
    searchParams = new URLSearchParams('mode=docs');
    const user = userEvent.setup();
    render(<HomeContent />);

    await user.click(screen.getByRole('button', { name: '질의 입력' }));
    await user.click(screen.getByRole('button', { name: '문서 검색' }));

    expect(push).toHaveBeenCalledWith(
      '/hybrid-search?q=%EC%A7%80%EB%82%9C%EC%A3%BC+%EA%B2%B0%EC%A0%9C+%EB%A1%A4%EB%B0%B1&smart_filter=true',
    );
  });

  it('빈 입력으로 docs submit하면 이동하지 않는다', async () => {
    searchParams = new URLSearchParams('mode=docs');
    const user = userEvent.setup();
    render(<HomeContent />);

    await user.click(screen.getByRole('button', { name: '문서 검색' }));

    expect(push).not.toHaveBeenCalled();
  });
});
