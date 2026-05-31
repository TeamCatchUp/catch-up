import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { slackOriginalPreviewResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';

import SlackOriginalPanelPreview from './SlackOriginalPanelPreview';

describe('SlackOriginalPanelPreview', () => {
  it('renders header, date indicator, comment divider, and messages', () => {
    render(<SlackOriginalPanelPreview response={slackOriginalPreviewResponse} />);

    expect(screen.getByText('slack-bot-test')).toBeInTheDocument();
    expect(screen.getByText('2개의 댓글')).toBeInTheDocument();
    expect(screen.getAllByText(/작성자명/).length).toBeGreaterThan(0);
    expect(screen.getByText('CatchUpQA')).toBeInTheDocument();
  });
});
