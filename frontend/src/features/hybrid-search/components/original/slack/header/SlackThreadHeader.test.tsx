import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SlackThreadHeader from './SlackThreadHeader';

describe('SlackThreadHeader', () => {
  it('renders channel and participants with truncation containers', () => {
    render(<SlackThreadHeader channelName="slack-bot-test" participantNames={['참여자 1', '참여자 2']} />);

    expect(screen.getByText('slack-bot-test')).toHaveClass('truncate');
    expect(screen.getByText('참여자 1, 참여자 2')).toHaveClass('truncate');
  });
});
