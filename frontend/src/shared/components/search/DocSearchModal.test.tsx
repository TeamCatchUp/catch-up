import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/shared/hooks/useSearchHistoryEntries', () => ({
  useSearchHistoryEntries: () => ({ entries: [], isLoading: false }),
}));

import DocSearchModal from './DocSearchModal';

const onOpenChange = vi.fn();

beforeEach(() => {
  mockPush.mockClear();
  onOpenChange.mockClear();
});

afterEach(() => {
  vi.clearAllMocks();
});

const openModal = () => render(<DocSearchModal open onOpenChange={onOpenChange} historyEntries={[]} />);

describe('DocSearchModal', () => {
  it('닫혀 있으면 아무것도 렌더하지 않는다', () => {
    render(<DocSearchModal open={false} onOpenChange={onOpenChange} historyEntries={[]} />);

    expect(screen.queryByPlaceholderText('업무, 채널 또는 문서를 검색해보세요')).not.toBeInTheDocument();
  });

  it('검색어를 넣고 엔터를 치면 결과 페이지로 보내고 닫는다', async () => {
    const user = userEvent.setup();
    openModal();

    await user.type(screen.getByPlaceholderText('업무, 채널 또는 문서를 검색해보세요'), '지난주 결제 롤백{Enter}');

    expect(onOpenChange).toHaveBeenCalledWith(false);
    const url = mockPush.mock.calls[0]![0] as string;
    const params = new URL(url, 'http://localhost').searchParams;
    expect(url.startsWith('/hybrid-search?')).toBe(true);
    expect(params.get('q')).toBe('지난주 결제 롤백');
    expect(params.get('smart_filter')).toBe('true');
  });

  it('빈 검색어로는 이동하지 않는다', async () => {
    const user = userEvent.setup();
    openModal();

    await user.click(screen.getByRole('button', { name: '검색' }));

    expect(mockPush).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it('AI 모드는 입력을 q로 실어 홈으로 보낸다', async () => {
    const user = userEvent.setup();
    openModal();

    await user.type(screen.getByPlaceholderText('업무, 채널 또는 문서를 검색해보세요'), '배포 롤백');
    await user.click(screen.getByRole('button', { name: 'AI 모드' }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(mockPush).toHaveBeenCalledWith(`/?q=${encodeURIComponent('배포 롤백')}`);
  });

  it('입력이 비어 있으면 AI 모드는 홈으로만 보낸다', async () => {
    const user = userEvent.setup();
    openModal();

    await user.click(screen.getByRole('button', { name: 'AI 모드' }));

    expect(mockPush).toHaveBeenCalledWith('/');
  });

  it('시안에 없는 닫기 버튼을 만들지 않는다', () => {
    openModal();

    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument();
  });
});
