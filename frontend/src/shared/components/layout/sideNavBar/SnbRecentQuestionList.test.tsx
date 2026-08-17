import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockUsePathname = vi.fn<() => string>();

vi.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
}));

const mockQueryResult = {
  data: { pages: [{ items: [] as { title: string; session_id: string }[] }] },
  hasNextPage: false,
  isFetchingNextPage: false,
  fetchNextPage: vi.fn(),
};

vi.mock('@tanstack/react-query', () => ({
  useInfiniteQuery: () => mockQueryResult,
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock('@/shared/queries/chatroom.queries', () => ({
  chatQueries: { all: () => ['chatrooms'], recentRoomsInfinite: () => ({}) },
}));

import SnbRecentQuestionList from './SnbRecentQuestionList';

beforeEach(() => {
  mockUsePathname.mockReturnValue('/');
  mockQueryResult.data = {
    pages: [
      {
        items: [
          { title: '연동 테스트 중단 리스크', session_id: 'session-1' },
          { title: '환불 정책 문의', session_id: 'session-2' },
        ],
      },
    ],
  };
  mockQueryResult.isFetchingNextPage = false;
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('SnbRecentQuestionList', () => {
  it('행을 링크로 렌더해 새 탭·미들클릭이 살아 있다', () => {
    render(<SnbRecentQuestionList />);

    expect(screen.getByRole('link', { name: '연동 테스트 중단 리스크' })).toHaveAttribute('href', '/chat/session-1');
    expect(screen.getByRole('link', { name: '환불 정책 문의' })).toHaveAttribute('href', '/chat/session-2');
  });

  it('현재 보고 있는 대화가 활성이다', () => {
    mockUsePathname.mockReturnValue('/chat/session-2');
    render(<SnbRecentQuestionList />);

    expect(screen.getByRole('link', { name: '환불 정책 문의' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: '연동 테스트 중단 리스크' })).not.toHaveAttribute('aria-current');
  });

  it('다음 페이지를 부르는 동안에만 진행 문구를 보여준다', () => {
    const { unmount } = render(<SnbRecentQuestionList />);
    expect(screen.queryByText('불러오는 중...')).toBeNull();
    unmount();

    mockQueryResult.isFetchingNextPage = true;
    render(<SnbRecentQuestionList />);
    expect(screen.getByText('불러오는 중...')).toBeInTheDocument();
  });

  it('목록이 비어도 대체 문구를 만들지 않는다', () => {
    mockQueryResult.data = { pages: [{ items: [] }] };
    const { container } = render(<SnbRecentQuestionList />);

    expect(container.textContent).not.toMatch(/없습니다|비어|다시 시도|실패/);
  });
});
