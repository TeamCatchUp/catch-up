import { describe, expect, it } from 'vitest';

import type { SlackBlockRaw, SlackUserMetadata } from '@/features/hybrid-search/types/slackOriginalApi';

import { parseSlackBlocks } from './parseSlackBlocks';

const usersById: Record<string, SlackUserMetadata> = {
  U_REPLY: { id: 'U_REPLY', display_name: '참여자 1' },
};

describe('parseSlackBlocks', () => {
  it('parses rich text sections, lists, quotes, and code blocks', () => {
    const blocks: SlackBlockRaw[] = [
      {
        type: 'rich_text',
        elements: [
          {
            type: 'rich_text_section',
            elements: [
              { type: 'user', user_id: 'U_REPLY' },
              { type: 'text', text: ' Inline code', style: { code: true } },
              { type: 'emoji', unicode: '1f972', name: 'smiling_face_with_tear' },
              { type: 'emoji', name: 'smile' },
            ],
          },
          {
            type: 'rich_text_list',
            style: 'ordered',
            offset: 2,
            elements: [
              { type: 'rich_text_section', elements: [{ type: 'text', text: '첫 번째' }] },
              { type: 'rich_text_section', elements: [{ type: 'text', text: '두 번째' }] },
            ],
          },
          {
            type: 'rich_text_quote',
            elements: [{ type: 'text', text: '인용' }],
          },
          {
            type: 'rich_text_preformatted',
            elements: [{ type: 'text', text: 'const ok = true;' }],
          },
        ],
      },
    ];

    expect(parseSlackBlocks(blocks, usersById)).toMatchObject([
      {
        type: 'paragraph',
        tokens: [
          { type: 'mention', label: '@참여자 1' },
          { type: 'text', text: ' Inline code', style: { code: true } },
          { type: 'emoji', label: '🥲' },
          { type: 'emoji', label: '😄' },
        ],
      },
      {
        type: 'ordered_list',
        start: 2,
        items: [[{ type: 'text', text: '첫 번째' }], [{ type: 'text', text: '두 번째' }]],
      },
      { type: 'quote', tokens: [{ type: 'text', text: '인용' }] },
      { type: 'code_block', text: 'const ok = true;' },
    ]);
  });

  it('uses fallback parsing for section fields', () => {
    const blocks: SlackBlockRaw[] = [
      {
        type: 'section',
        text: { type: 'mrkdwn', text: '<@U_REPLY> *확인*' },
        fields: [{ type: 'mrkdwn', text: '<https://example.com|문서>' }],
      },
    ];

    const parsed = parseSlackBlocks(blocks, usersById);

    expect(parsed[0]).toMatchObject({
      type: 'paragraph',
      tokens: expect.arrayContaining([
        { type: 'mention', label: '@참여자 1', style: undefined },
        { type: 'text', text: '확인', style: { bold: true } },
      ]),
    });
    expect(parsed[1]).toMatchObject({
      type: 'paragraph',
      tokens: [{ type: 'link', href: 'https://example.com', text: '문서', style: undefined }],
    });
  });

  it('falls back to colon emoji names when rich text unicode is invalid', () => {
    const blocks: SlackBlockRaw[] = [
      {
        type: 'rich_text',
        elements: [
          {
            type: 'rich_text_section',
            elements: [{ type: 'emoji', unicode: 'not-hex', name: 'custom_emoji' }],
          },
        ],
      },
    ];

    expect(parseSlackBlocks(blocks, usersById)).toMatchObject([
      {
        type: 'paragraph',
        tokens: [{ type: 'emoji', label: ':custom_emoji:' }],
      },
    ]);
  });

  it('keeps rich text code spans with underscores as one token inside lists', () => {
    const blocks: SlackBlockRaw[] = [
      {
        type: 'rich_text',
        elements: [
          {
            type: 'rich_text_list',
            elements: [
              {
                type: 'rich_text_section',
                elements: [
                  { type: 'emoji', name: 'white_check_mark', unicode: '2705' },
                  { type: 'text', text: ' Ingestion 과정에서 CatchUp 봇의 답변이 ' },
                  { type: 'text', text: '[CATCH_UP_ANSWER]', style: { code: true } },
                  { type: 'text', text: '로 치환되도록 수정 완료' },
                ],
              },
            ],
          },
        ],
      },
    ];

    expect(parseSlackBlocks(blocks, usersById)).toMatchObject([
      {
        type: 'bullet_list',
        items: [
          [
            { type: 'emoji', label: '✅' },
            { type: 'text', text: ' Ingestion 과정에서 CatchUp 봇의 답변이 ' },
            { type: 'text', text: '[CATCH_UP_ANSWER]', style: { code: true } },
            { type: 'text', text: '로 치환되도록 수정 완료' },
          ],
        ],
      },
    ]);
  });
});
