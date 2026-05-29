import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import DocsQueryBox from './DocsQueryBox';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

describe('DocsQueryBox', () => {
  it('submits smart_filter=true with query, manual tools, and date range', async () => {
    mockPush.mockClear();
    const user = userEvent.setup();
    render(
      <DocsQueryBox
        selectedSources={['slack']}
        dateRange={{ from: new Date(2026, 4, 13), to: new Date(2026, 4, 14) }}
        smartFilter={true}
      />,
    );

    await user.type(screen.getByRole('textbox'), '회의록');
    await user.click(screen.getByRole('button', { name: '보내기' }));

    const url = mockPush.mock.calls[0]![0] as string;
    const searchParams = new URL(url, 'http://localhost').searchParams;
    expect(searchParams.get('q')).toBe('회의록');
    expect(searchParams.get('tools')).toBe('slack');
    expect(searchParams.get('start')).toBe('2026-05-13');
    expect(searchParams.get('end')).toBe('2026-05-14');
    expect(searchParams.get('smart_filter')).toBe('true');
  });

  it('submits smart_filter=false explicitly', async () => {
    mockPush.mockClear();
    const user = userEvent.setup();
    render(<DocsQueryBox selectedSources={[]} dateRange={undefined} smartFilter={false} />);

    await user.type(screen.getByRole('textbox'), '기본 검색');
    await user.click(screen.getByRole('button', { name: '보내기' }));

    const url = mockPush.mock.calls[0]![0] as string;
    const searchParams = new URL(url, 'http://localhost').searchParams;
    expect(searchParams.get('q')).toBe('기본 검색');
    expect(searchParams.has('tools')).toBe(false);
    expect(searchParams.get('smart_filter')).toBe('false');
  });
});
