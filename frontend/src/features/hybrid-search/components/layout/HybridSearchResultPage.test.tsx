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
  default: ({ onAiModeClick }: { onAiModeClick?: () => void }) => (
    <button type="button" onClick={onAiModeClick}>
      AI 모드
    </button>
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
});
