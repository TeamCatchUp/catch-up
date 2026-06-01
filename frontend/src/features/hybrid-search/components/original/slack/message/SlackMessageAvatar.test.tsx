import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SlackMessageAvatar from './SlackMessageAvatar';

describe('SlackMessageAvatar', () => {
  it('uses profile fallback for users without an avatar URL', () => {
    render(<SlackMessageAvatar name="작성자" avatarUrl={null} avatarSource="none" kind="user" />);

    expect(screen.getByLabelText('작성자')).toBeInTheDocument();
  });

  it('uses the bot fallback and badge for bots without an avatar URL', () => {
    render(<SlackMessageAvatar name="CatchUpQA" avatarUrl={null} avatarSource="none" kind="bot" />);

    expect(screen.getByLabelText('CatchUpQA')).toBeInTheDocument();
    expect(screen.getByLabelText('CatchUpQA').parentElement).toHaveClass('bg-fill-primary', 'size-9');
  });

  it('keeps badge for bot_profile avatar URLs', () => {
    const { container } = render(
      <SlackMessageAvatar
        name="CatchUpQA"
        avatarUrl="https://a.slack-edge.com/80588/img/plugins/app/bot_36.png"
        avatarSource="bot_profile"
        kind="bot"
      />,
    );

    const avatarWrapper = container.firstElementChild;

    expect(avatarWrapper).toHaveClass('size-9');
    expect(avatarWrapper).not.toHaveClass('bg-fill-primary');
    expect(container.querySelector('svg[aria-hidden="true"]')).toBeInTheDocument();
  });

  it('hides badge for top-level message icon avatar URLs', () => {
    const { container } = render(
      <SlackMessageAvatar
        name="팀원B / Catch Up"
        avatarUrl="https://example.com/slack-app-icon.png"
        avatarSource="message_icons"
        kind="bot"
      />,
    );

    expect(container.firstElementChild).toHaveClass('size-9');
    expect(container.firstElementChild).not.toHaveClass('bg-fill-primary');
    expect(container.querySelector('svg[aria-hidden="true"]')).not.toBeInTheDocument();
  });
});
