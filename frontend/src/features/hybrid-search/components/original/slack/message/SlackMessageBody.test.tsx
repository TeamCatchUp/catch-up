import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { SlackMessageView } from '@/features/hybrid-search/types/slackOriginalModel';

import SlackMessageBody from './SlackMessageBody';

describe('SlackMessageBody', () => {
  it('renders text, files, and link previews', () => {
    const message: SlackMessageView = {
      id: '1',
      ts: '1779601372.378609',
      threadTs: '1779601372.378609',
      author: { id: 'U1', name: '작성자', avatarUrl: null, avatarSource: 'none', kind: 'user' },
      timeLabel: '02:33 PM',
      editedLabel: '',
      dateKey: '2026-05-24T05:42:52.378Z',
      blocks: [{ type: 'paragraph', tokens: [{ type: 'text', text: '본문' }] }],
      files: [
        {
          id: 'F_DOC',
          name: 'doc.pdf',
          mimetype: 'application/pdf',
          permalink: 'https://catchup.slack.com/files/F_DOC',
        },
        {
          id: 'F_IMG',
          name: 'image.png',
          mimetype: 'image/png',
          thumb_360: 'https://placehold.co/360x360/png',
        },
        {
          id: 'F_IMG_NO_THUMB',
          name: 'fallback-image.png',
          mimetype: 'image/png',
          permalink: 'https://catchup.slack.com/files/F_IMG_NO_THUMB',
        },
      ],
      attachments: [{ id: 1, title: '링크 카드', title_link: 'https://example.com', text: '설명' }],
    };

    render(
      <SlackMessageBody message={message} originalUrl="https://catchup.slack.com/archives/C1/p1779601372378609" />,
    );

    expect(screen.getByText('본문')).toBeInTheDocument();
    expect(screen.getByText('doc.pdf')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /doc.pdf/i })).toHaveAttribute(
      'href',
      'https://catchup.slack.com/archives/C1/p1779601372378609',
    );
    expect(screen.getByText('fallback-image.png')).toBeInTheDocument();
    expect(screen.getByText('image.png')).toBeInTheDocument();
    expect(screen.queryByAltText('image.png')).not.toBeInTheDocument();
    expect(screen.getByText('링크 카드')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^image\.png\s+png$/i })).toHaveAttribute(
      'href',
      'https://catchup.slack.com/archives/C1/p1779601372378609',
    );
  });
});
