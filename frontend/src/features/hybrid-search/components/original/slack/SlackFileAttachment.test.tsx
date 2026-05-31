import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SlackFileAttachment from './SlackFileAttachment';

describe('SlackFileAttachment', () => {
  it('uses Slack permalink directly and never needs the original file-url API', () => {
    render(
      <SlackFileAttachment
        file={{
          id: 'F1',
          name: 'spec.pdf',
          mimetype: 'application/pdf',
          size: 1024,
          permalink: 'https://catchup.slack.com/files/F1',
        }}
      />,
    );

    expect(screen.getByRole('link', { name: /spec.pdf/i })).toHaveAttribute(
      'href',
      'https://catchup.slack.com/files/F1',
    );
  });
});
