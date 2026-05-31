import { describe, expect, it } from 'vitest';

import type { SlackUserMetadata } from '@/features/hybrid-search/types/slackOriginalApi';

import { parseSlackTextFallback } from './parseSlackTextFallback';

const usersById: Record<string, SlackUserMetadata> = {
  U_REPLY: { id: 'U_REPLY', display_name: '참여자 1' },
};

describe('parseSlackTextFallback', () => {
  it('parses mentions, links, styles, and line breaks', () => {
    const [block] = parseSlackTextFallback('<@U_REPLY> *bold* `code`\n<https://example.com|링크>', usersById);

    expect(block).toMatchObject({
      type: 'paragraph',
      tokens: [
        { type: 'mention', label: '@참여자 1' },
        { type: 'text', text: ' ' },
        { type: 'text', text: 'bold', style: { bold: true } },
        { type: 'text', text: ' ' },
        { type: 'text', text: 'code', style: { code: true } },
        { type: 'line_break' },
        { type: 'link', href: 'https://example.com', text: '링크' },
      ],
    });
  });

  it('keeps unsafe links as text', () => {
    const [block] = parseSlackTextFallback('<javascript:alert(1)|bad>', usersById);

    expect(block).toMatchObject({
      type: 'paragraph',
      tokens: [{ type: 'text', text: 'bad' }],
    });
  });
});
