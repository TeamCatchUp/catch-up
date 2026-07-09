import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Message } from '@/features/chat/types';

import { useRagScroll } from './useRagScroll';

interface RenderProps {
  messages: Message[];
  scrollToMessageId: string | null;
  scrollToLatestOnGeneration: boolean;
}

const messages: Message[] = [
  {
    id: 'user-1',
    role: 'user',
    content: 'first',
    timestamp: '2026-07-09T09:00:00.000Z',
  },
  {
    id: 'assistant-1',
    role: 'assistant',
    content: 'answer',
    timestamp: '2026-07-09T09:00:01.000Z',
  },
  {
    id: 'user-2',
    role: 'user',
    content: 'second',
    timestamp: '2026-07-09T09:00:02.000Z',
  },
];

const createScrollElement = () => {
  const element = document.createElement('div');
  element.scrollIntoView = vi.fn();
  return element;
};

describe('useRagScroll generation fallback', () => {
  const originalRequestAnimationFrame = window.requestAnimationFrame;

  beforeEach(() => {
    window.requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
  });

  afterEach(() => {
    window.requestAnimationFrame = originalRequestAnimationFrame;
    vi.restoreAllMocks();
  });

  it('scrolls to the latest Q&A pair once when generation is active without scrollTo', async () => {
    const firstElement = createScrollElement();
    const latestElement = createScrollElement();

    const { result, rerender } = renderHook(
      (props: RenderProps) =>
        useRagScroll({
          messages: props.messages,
          scrollToMessageId: props.scrollToMessageId,
          scrollToLatestOnGeneration: props.scrollToLatestOnGeneration,
        }),
      {
        initialProps: {
          messages,
          scrollToMessageId: null as string | null,
          scrollToLatestOnGeneration: false,
        },
      },
    );

    result.current.qaRefs.current.set(0, firstElement);
    result.current.qaRefs.current.set(1, latestElement);

    rerender({
      messages,
      scrollToMessageId: null,
      scrollToLatestOnGeneration: true,
    });

    await waitFor(() => {
      expect(latestElement.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
    });
    expect(firstElement.scrollIntoView).not.toHaveBeenCalled();

    rerender({
      messages: [...messages],
      scrollToMessageId: null,
      scrollToLatestOnGeneration: true,
    });

    expect(latestElement.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it('keeps explicit scrollTo navigation ahead of generation fallback', async () => {
    const firstElement = createScrollElement();
    const latestElement = createScrollElement();

    const { result, rerender } = renderHook(
      (props: RenderProps) =>
        useRagScroll({
          messages: props.messages,
          scrollToMessageId: props.scrollToMessageId,
          scrollToLatestOnGeneration: props.scrollToLatestOnGeneration,
        }),
      {
        initialProps: {
          messages,
          scrollToMessageId: null as string | null,
          scrollToLatestOnGeneration: false,
        },
      },
    );

    result.current.qaRefs.current.set(0, firstElement);
    result.current.qaRefs.current.set(1, latestElement);

    rerender({
      messages,
      scrollToMessageId: 'user-1',
      scrollToLatestOnGeneration: true,
    });

    await waitFor(() => {
      expect(firstElement.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
    });
    expect(latestElement.scrollIntoView).not.toHaveBeenCalled();
  });
});
