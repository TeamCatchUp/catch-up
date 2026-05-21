import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { SearchHistoryEntry } from '@/shared/types/searchHistory';

import SearchHistoryList from './SearchHistoryList';

const FIXED_NOW = new Date('2026-05-12T12:00:00');

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(FIXED_NOW);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('SearchHistoryList', () => {
  it('isLoading=true + 빈 배열이면 null을 반환한다', () => {
    const { container } = render(<SearchHistoryList entries={[]} isLoading={true} />);
    expect(container.firstChild).toBeNull();
  });

  it('isLoading=false + 빈 배열이면 안내 메시지를 표시한다', () => {
    render(<SearchHistoryList entries={[]} isLoading={false} />);
    expect(screen.getByText('최근 검색 기록이 없습니다')).toBeInTheDocument();
  });

  it('항목들을 오늘/최근 7일/이전 그룹으로 분류한다', () => {
    const entries: SearchHistoryEntry[] = [
      { id: 'a', query: '오늘 항목', createdAt: new Date('2026-05-12T09:00:00') },
      { id: 'b', query: '최근 7일 항목', createdAt: new Date('2026-05-08T09:00:00') },
      { id: 'c', query: '이전 항목', createdAt: new Date('2026-04-01T09:00:00') },
    ];

    render(<SearchHistoryList entries={entries} />);

    expect(screen.getByText('오늘')).toBeInTheDocument();
    expect(screen.getByText('최근 7일')).toBeInTheDocument();
    expect(screen.getByText('이전')).toBeInTheDocument();
    expect(screen.getByText('오늘 항목')).toBeInTheDocument();
    expect(screen.getByText('최근 7일 항목')).toBeInTheDocument();
    expect(screen.getByText('이전 항목')).toBeInTheDocument();
  });

  it('하나의 그룹에만 속하는 경우 다른 그룹 캡션은 미렌더', () => {
    const entries: SearchHistoryEntry[] = [
      { id: 'a', query: '오늘만', createdAt: new Date('2026-05-12T09:00:00') },
    ];

    render(<SearchHistoryList entries={entries} />);

    expect(screen.getByText('오늘')).toBeInTheDocument();
    expect(screen.queryByText('최근 7일')).not.toBeInTheDocument();
    expect(screen.queryByText('이전')).not.toBeInTheDocument();
  });

  it('maxPerGroup으로 각 그룹의 상한을 적용한다', () => {
    const entries: SearchHistoryEntry[] = [
      { id: '1', query: '오늘1', createdAt: new Date('2026-05-12T11:00:00') },
      { id: '2', query: '오늘2', createdAt: new Date('2026-05-12T10:00:00') },
      { id: '3', query: '오늘3', createdAt: new Date('2026-05-12T09:00:00') },
      { id: '4', query: '오늘4', createdAt: new Date('2026-05-12T08:00:00') },
      { id: '5', query: '오늘5', createdAt: new Date('2026-05-12T07:00:00') },
    ];

    render(<SearchHistoryList entries={entries} maxPerGroup={3} />);

    expect(screen.getByText('오늘1')).toBeInTheDocument();
    expect(screen.getByText('오늘3')).toBeInTheDocument();
    expect(screen.queryByText('오늘4')).not.toBeInTheDocument();
    expect(screen.queryByText('오늘5')).not.toBeInTheDocument();
  });

  it('항목 클릭 시 onItemClick이 entry를 인자로 호출된다', () => {
    const handle = vi.fn<(entry: SearchHistoryEntry) => void>();
    const entries: SearchHistoryEntry[] = [
      { id: '1', query: '클릭대상', createdAt: new Date('2026-05-12T09:00:00') },
    ];

    render(<SearchHistoryList entries={entries} onItemClick={handle} />);
    fireEvent.click(screen.getByRole('button', { name: /클릭대상/ }));

    expect(handle).toHaveBeenCalledTimes(1);
    expect(handle.mock.calls[0]?.[0]?.id).toBe('1');
  });
});
