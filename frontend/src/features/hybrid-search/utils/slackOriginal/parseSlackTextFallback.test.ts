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

  it('decodes Slack text entities without breaking special tokens', () => {
    const [block] = parseSlackTextFallback(
      'A -&gt; B &amp; C <https://example.com?a=1&amp;b=2|A &amp; B>',
      usersById,
    );

    expect(block).toMatchObject({
      type: 'paragraph',
      tokens: [
        { type: 'text', text: 'A -> B & C ' },
        { type: 'link', href: 'https://example.com?a=1&b=2', text: 'A & B' },
      ],
    });
  });

  it('resolves standard colon emoji before italic parsing', () => {
    const [block] = parseSlackTextFallback(':busts_in_silhouette: :smile: :catchup_logo: _italic_', usersById);

    expect(block).toMatchObject({
      type: 'paragraph',
      tokens: [
        { type: 'emoji', label: '👥' },
        { type: 'text', text: ' ' },
        { type: 'emoji', label: '😄' },
        { type: 'text', text: ' ' },
        { type: 'emoji', label: ':catchup_logo:' },
        { type: 'text', text: ' ' },
        { type: 'text', text: 'italic', style: { italic: true } },
      ],
    });
  });
});
