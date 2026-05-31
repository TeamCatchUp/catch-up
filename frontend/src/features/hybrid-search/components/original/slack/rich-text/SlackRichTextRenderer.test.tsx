import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { SlackBlockView } from '@/features/hybrid-search/types/slackOriginalModel';

import SlackRichTextRenderer from './SlackRichTextRenderer';

describe('SlackRichTextRenderer', () => {
  it('renders rich tokens, lists, quote, and code block', () => {
    const blocks: SlackBlockView[] = [
      {
        type: 'paragraph',
        tokens: [
          { type: 'mention', label: '@참여자 1' },
          { type: 'text', text: ' Inline code', style: { code: true } },
          { type: 'line_break' },
          { type: 'link', href: 'https://example.com', text: '문서' },
        ],
      },
      { type: 'bullet_list', items: [[{ type: 'text', text: 'bullet' }]] },
      { type: 'ordered_list', start: 1, items: [[{ type: 'text', text: 'ordered' }]] },
      { type: 'quote', tokens: [{ type: 'text', text: 'quote' }] },
      { type: 'code_block', text: 'const ok = true;' },
    ];

    render(<SlackRichTextRenderer blocks={blocks} />);

    expect(screen.getByText('@참여자 1')).toBeInTheDocument();
    expect(screen.getByText(/Inline code/)).toHaveClass('text-status-cautionary');
    expect(screen.getByRole('link', { name: '문서' })).toHaveAttribute('href', 'https://example.com');
    expect(screen.getByText('bullet')).toBeInTheDocument();
    expect(screen.getByText('ordered')).toBeInTheDocument();
    expect(screen.getByText('quote')).toBeInTheDocument();
    expect(screen.getByText('const ok = true;')).toHaveClass('custom-scrollbar', 'max-h-62.5', 'overflow-auto');
  });
});
