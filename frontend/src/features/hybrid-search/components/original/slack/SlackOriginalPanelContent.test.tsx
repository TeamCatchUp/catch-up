import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';

import SlackOriginalPanelContent from './SlackOriginalPanelContent';

type ObserverCallback = IntersectionObserverCallback;

const observers: Array<{ callback: ObserverCallback; disconnect: ReturnType<typeof vi.fn> }> = [];

function installIntersectionObserverMock() {
  observers.length = 0;

  vi.stubGlobal(
    'IntersectionObserver',
    vi.fn(function IntersectionObserverMock(callback: ObserverCallback) {
      const observer = {
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn(),
      };
      observers.push({ callback, disconnect: observer.disconnect });
      return observer;
    }),
  );
}

afterEach(() => {
  observers.length = 0;
  vi.unstubAllGlobals();
});

describe('SlackOriginalPanelContent', () => {
  it('renders header, date indicator, comment divider, and messages from pages', () => {
    render(
      <SlackOriginalPanelContent
        pages={[slackOriginalThreadResponse]}
        hasNextPage={false}
        isFetchingNextPage={false}
        onLoadNextPage={vi.fn()}
      />,
    );

    expect(screen.getByText('slack-bot-test')).toBeInTheDocument();
    expect(screen.getByText('2개의 댓글')).toBeInTheDocument();
    expect(screen.getAllByText(/작성자명/).length).toBeGreaterThan(0);
    expect(screen.getByText('CatchUpQA')).toBeInTheDocument();
  });

  it('requests the next page when the sentinel intersects', () => {
    installIntersectionObserverMock();
    const onLoadNextPage = vi.fn();

    render(
      <SlackOriginalPanelContent
        pages={[{ ...slackOriginalThreadResponse, next_cursor: 'cursor-1' }]}
        hasNextPage
        isFetchingNextPage={false}
        onLoadNextPage={onLoadNextPage}
      />,
    );

    act(() => {
      observers[0]?.callback(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    expect(onLoadNextPage).toHaveBeenCalledTimes(1);
  });

  it('does not request another page while a page is already fetching', () => {
    installIntersectionObserverMock();
    const onLoadNextPage = vi.fn();

    render(
      <SlackOriginalPanelContent
        pages={[{ ...slackOriginalThreadResponse, next_cursor: 'cursor-1' }]}
        hasNextPage
        isFetchingNextPage
        onLoadNextPage={onLoadNextPage}
      />,
    );

    expect(observers).toHaveLength(0);
    expect(onLoadNextPage).not.toHaveBeenCalled();
    expect(screen.queryByText('댓글을 더 불러오는 중')).not.toBeInTheDocument();
  });
});
