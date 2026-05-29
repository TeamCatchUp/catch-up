import type { DateRange } from 'react-day-picker';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ToolFilter } from '../../types/hybridSearchApi';
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
    draftKeyword,
    onDraftKeywordChange,
    onDraftChipsChange,
    onDraftDateRangeChange,
    onAiModeClick,
    onSubmit,
    onSmartFilterChange,
    smartFilter,
  }: {
    draftKeyword?: string;
    onDraftKeywordChange?: (value: string) => void;
    draftChips?: ToolFilter[];
    onDraftChipsChange?: (next: ToolFilter[]) => void;
    draftDateRange?: DateRange;
    onDraftDateRangeChange?: (next: DateRange | undefined) => void;
    onAiModeClick?: () => void;
    onSubmit?: () => void;
    onSmartFilterChange?: (next: boolean) => void;
    smartFilter?: boolean;
  }) => (
    <div>
      <span data-testid="draft-keyword">{draftKeyword}</span>
      <button type="button" onClick={() => onDraftKeywordChange?.('draft keyword')}>
        draft 검색어 변경
      </button>
      <button type="button" onClick={() => onDraftChipsChange?.(['slack'])}>
        draft 필터 변경
      </button>
      <button
        type="button"
        onClick={() => onDraftDateRangeChange?.({ from: new Date(2026, 4, 20), to: new Date(2026, 4, 21) })}
      >
        draft 날짜 변경
      </button>
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

  it('smart filter 변경 시 미제출 draft 검색어와 수동 필터를 URL에 반영하지 않는다', async () => {
    mockSearchParams.set('q', 'committed');
    mockSearchParams.set('tools', 'github');
    mockSearchParams.set('start', '2026-05-01');
    mockSearchParams.set('end', '2026-05-02');
    mockSearchParams.set('smart_filter', 'true');
    const user = userEvent.setup();

    render(<HybridSearchResultPage />);

    await user.click(screen.getByRole('button', { name: 'draft 검색어 변경' }));
    await user.click(screen.getByRole('button', { name: 'draft 필터 변경' }));
    await user.click(screen.getByRole('button', { name: 'draft 날짜 변경' }));
    await user.click(screen.getByRole('button', { name: '스마트 필터 toggle' }));

    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=committed');
    expect(url).toContain('tools=github');
    expect(url).toContain('start=2026-05-01');
    expect(url).toContain('end=2026-05-02');
    expect(url).toContain('smart_filter=false');
    expect(url).not.toContain('draft');
    expect(url).not.toContain('slack');
    expect(url).not.toContain('2026-05-20');
  });
});
