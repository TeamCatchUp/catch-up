import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HybridSearchResultPage from './HybridSearchResultPage';

const mockPush = vi.fn();
const mockReplace = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock('../../hooks/useHybridSearch', () => ({
  useHybridSearch: () => ({ data: { results: [] } }),
}));

vi.mock('./ResultPageHeader', () => ({
  default: ({
    onAiModeClick,
    onSubmit,
    onSmartFilterChange,
    smartFilter,
  }: {
    onAiModeClick?: () => void;
    onSubmit?: () => void;
    onSmartFilterChange?: (next: boolean) => void;
    smartFilter?: boolean;
  }) => (
    <div>
      <button type="button" onClick={onAiModeClick}>
        AI 모드
      </button>
      <button type="button" onClick={() => onSmartFilterChange?.(!smartFilter)}>
        스마트 필터 toggle
      </button>
      <button type="button" onClick={onSubmit}>
        검색
      </button>
    </div>
  ),
}));

vi.mock('./ResultPageBody', () => ({
  default: ({ children, side }: { children: React.ReactNode; side: React.ReactNode }) => (
    <div>
      {children}
      {side}
    </div>
  ),
}));

vi.mock('../original/OriginalPanel', () => ({
  default: () => <div data-testid="original-panel" />,
}));

vi.mock('../result-list/ResultListSection', () => ({
  default: () => <div data-testid="result-list" />,
}));

beforeEach(() => {
  mockPush.mockClear();
  mockReplace.mockClear();
  for (const key of Array.from(mockSearchParams.keys())) mockSearchParams.delete(key);
});

describe('HybridSearchResultPage', () => {
  it('AI 모드 클릭 시 draft 검색어를 /search q 파라미터로 전달한다', async () => {
    mockSearchParams.set('q', '검색어 text');
    const user = userEvent.setup();

    render(<HybridSearchResultPage />);

    await user.click(screen.getByRole('button', { name: 'AI 모드' }));

    expect(mockPush).toHaveBeenCalledWith('/search?q=%EA%B2%80%EC%83%89%EC%96%B4+text');
  });

  it('AI 모드 클릭 시 draft 검색어가 비어 있으면 /search로 이동한다', async () => {
    const user = userEvent.setup();

    render(<HybridSearchResultPage />);

    await user.click(screen.getByRole('button', { name: 'AI 모드' }));

    expect(mockPush).toHaveBeenCalledWith('/search');
  });

  it('submit 시 smart_filter를 URL에 명시한다', async () => {
    mockSearchParams.set('q', '검색어 text');
    const user = userEvent.setup();

    render(<HybridSearchResultPage />);

    await user.click(screen.getByRole('button', { name: '검색' }));

    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('smart_filter=true');
  });

  it('smart filter 변경 시 URL에 즉시 반영한다', async () => {
    mockSearchParams.set('q', '검색어 text');
    mockSearchParams.set('smart_filter', 'true');
    const user = userEvent.setup();

    render(<HybridSearchResultPage />);

    await user.click(screen.getByRole('button', { name: '스마트 필터 toggle' }));

    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('smart_filter=false');
  });
});
