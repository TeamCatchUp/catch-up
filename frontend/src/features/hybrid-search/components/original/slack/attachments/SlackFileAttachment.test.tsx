import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SlackFileAttachment from './SlackFileAttachment';

describe('SlackFileAttachment', () => {
  it('uses the Slack thread original URL instead of the file permalink', () => {
    render(
      <SlackFileAttachment
        originalUrl="https://catchup.slack.com/archives/C1/p1779424844293589"
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
      'https://catchup.slack.com/archives/C1/p1779424844293589',
    );
  });
});
