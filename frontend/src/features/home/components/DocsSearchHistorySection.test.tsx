import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import DocsSearchHistorySection from './DocsSearchHistorySection';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/shared/hooks/useSearchHistoryEntries', () => ({
  useSearchHistoryEntries: () => ({
    entries: [{ id: '1', query: '지난주 장애', createdAt: new Date('2026-05-29T00:00:00Z') }],
    isLoading: false,
  }),
}));

describe('DocsSearchHistorySection', () => {
  it('history click carries selected filters and smart_filter', async () => {
    mockPush.mockClear();
    const user = userEvent.setup();
    render(
      <DocsSearchHistorySection
        selectedSources={['confluence']}
        dateRange={{ from: new Date(2026, 4, 13), to: new Date(2026, 4, 14) }}
        smartFilter={true}
      />,
    );

    await user.click(screen.getByText('지난주 장애'));
    const url = mockPush.mock.calls[0]![0] as string;
    const searchParams = new URL(url, 'http://localhost').searchParams;
    expect(searchParams.get('q')).toBe('지난주 장애');
    expect(searchParams.get('tools')).toBe('confluence');
    expect(searchParams.get('start')).toBe('2026-05-13');
    expect(searchParams.get('end')).toBe('2026-05-14');
    expect(searchParams.get('smart_filter')).toBe('true');
  });
});
