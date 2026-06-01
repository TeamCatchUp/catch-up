import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SlackImageGrid from './SlackImageGrid';

describe('SlackImageGrid', () => {
  it('opens the Slack thread original URL when an image is clicked', () => {
    render(
      <SlackImageGrid
        originalUrl="https://catchup.slack.com/archives/C1/p1779601372378609"
        files={[{ id: 'F1', name: 'one.png', mimetype: 'image/png', thumb_360: 'https://placehold.co/360x360/png' }]}
      />,
    );

    expect(screen.getByRole('link', { name: 'one.png' })).toHaveAttribute(
      'href',
      'https://catchup.slack.com/archives/C1/p1779601372378609',
    );
  });

  it('moves horizontally with FAB buttons only when images overflow', async () => {
    render(
      <SlackImageGrid
        files={[
          { id: 'F1', name: 'one.png', mimetype: 'image/png', thumb_360: 'https://placehold.co/360x360/png' },
          { id: 'F2', name: 'two.png', mimetype: 'image/png', thumb_360: 'https://placehold.co/360x360/png' },
          { id: 'F3', name: 'three.png', mimetype: 'image/png', thumb_360: 'https://placehold.co/360x360/png' },
        ]}
      />,
    );

    const scroller = screen.getByTestId('slack-image-grid-scroll');
    Object.defineProperties(scroller, {
      clientWidth: { configurable: true, value: 333 },
      scrollWidth: { configurable: true, value: 380 },
      scrollLeft: { configurable: true, writable: true, value: 0 },
      scrollBy: { configurable: true, value: vi.fn() },
    });

    const leftButton = screen.getByRole('button', { name: '이미지 좌측으로 이동' });
    const rightButton = screen.getByRole('button', { name: '이미지 우측으로 이동' });

    fireEvent.scroll(scroller);

    await waitFor(() => {
      expect(leftButton).toHaveClass('opacity-0');
      expect(rightButton).toHaveClass('opacity-100');
    });

    fireEvent.click(rightButton);

    expect(scroller.scrollBy).toHaveBeenCalledWith({ left: 333 * 0.7, behavior: 'smooth' });
  });
});
