import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import type { SlackMessageView } from '@/features/hybrid-search/types/slackOriginalModel';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import SlackMessageItem from './SlackMessageItem';

describe('SlackMessageItem', () => {
  it('renders author, time, edited label, and body', () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
    render(<SlackMessageItem message={thread.messages[1]} />);

    expect(screen.getByText('CatchUpQA')).toBeInTheDocument();
    expect(screen.getByText('CatchUpQA')).toHaveClass('text-content-primary');
    expect(screen.getByText(/^\d{2}:\d{2}\s?(AM|PM)$/i)).toBeInTheDocument();
    expect(screen.getByText('편집됨')).toBeInTheDocument();
    expect(screen.getByText('Inline code')).toBeInTheDocument();
  });

  it('renders top-level message icon bots with normal author color', () => {
    const message: SlackMessageView = {
      id: '1779424844.293589',
      ts: '1779424844.293589',
      threadTs: '1779424844.293589',
      author: {
        id: 'B0TEST',
        name: '팀원B / Catch Up',
        avatarUrl: 'https://example.com/slack-app-icon.png',
        avatarSource: 'message_icons',
        kind: 'bot',
      },
      timeLabel: '01:40 PM',
      editedLabel: '',
      dateKey: '2026-05-31T04:40:44.293Z',
      blocks: [{ type: 'paragraph', tokens: [{ type: 'text', text: '본문' }] }],
      files: [],
      attachments: [],
    };

    render(<SlackMessageItem message={message} />);

    expect(screen.getByText('팀원B / Catch Up')).toHaveClass('text-content-alternative');
    expect(screen.getByText('팀원B / Catch Up')).not.toHaveClass('text-content-primary');
  });
});
