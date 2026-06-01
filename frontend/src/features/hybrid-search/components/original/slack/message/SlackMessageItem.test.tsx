import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slackOriginal/parseSlackOriginal';

import SlackMessageItem from './SlackMessageItem';

describe('SlackMessageItem', () => {
  it('renders author, time, edited label, and body', () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
    render(<SlackMessageItem message={thread.messages[1]} />);

    expect(screen.getByText('CatchUpQA')).toBeInTheDocument();
    expect(screen.getByText(/^\d{2}:\d{2}\s?(AM|PM)$/i)).toBeInTheDocument();
    expect(screen.getByText('편집됨')).toBeInTheDocument();
    expect(screen.getByText('Inline code')).toBeInTheDocument();
  });
});
