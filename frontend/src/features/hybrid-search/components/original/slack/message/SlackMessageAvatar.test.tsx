import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SlackMessageAvatar from './SlackMessageAvatar';

describe('SlackMessageAvatar', () => {
  it('uses profile fallback for users without an avatar URL', () => {
    render(<SlackMessageAvatar name="작성자" avatarUrl={null} kind="user" />);

    expect(screen.getByLabelText('작성자')).toBeInTheDocument();
  });

  it('uses the bot fallback and badge for bots without an avatar URL', () => {
    render(<SlackMessageAvatar name="CatchUpQA" avatarUrl={null} kind="bot" />);

    expect(screen.getByLabelText('CatchUpQA')).toBeInTheDocument();
    expect(screen.getByLabelText('CatchUpQA').parentElement).toHaveClass('bg-fill-primary', 'size-9');
  });

  it('does not apply fallback background when bot avatar URL exists and keeps badge', () => {
    const { container } = render(
      <SlackMessageAvatar
        name="CatchUpQA"
        avatarUrl="https://a.slack-edge.com/80588/img/plugins/app/bot_36.png"
        kind="bot"
      />,
    );

    const avatarWrapper = container.firstElementChild;

    expect(avatarWrapper).toHaveClass('size-9');
    expect(avatarWrapper).not.toHaveClass('bg-fill-primary');
    expect(container.querySelector('svg[aria-hidden="true"]')).toBeInTheDocument();
  });
});
