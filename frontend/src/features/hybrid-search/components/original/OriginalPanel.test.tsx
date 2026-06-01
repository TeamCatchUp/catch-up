import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import { server } from '@/test/msw/server';

import OriginalPanel from './OriginalPanel';

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('OriginalPanel', () => {
  it('renders empty state when documentId is missing', () => {
    render(<OriginalPanel connector={null} entityType={null} documentId={null} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText('표시할 원문이 없어요.')).toBeInTheDocument();
  });

  it('renders Slack original panel for Slack message sources', async () => {
    server.use(
      http.post('/api/v1/search/original', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body).toEqual({
          connector: 'slack',
          document_id: slackOriginalThreadResponse.document_id,
          next_cursor: null,
        });
        return HttpResponse.json(slackOriginalThreadResponse);
      }),
    );

    render(
      <OriginalPanel
        connector="slack"
        entityType="message"
        documentId={slackOriginalThreadResponse.document_id}
      />,
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(screen.getByText('slack-bot-test')).toBeInTheDocument());
    expect(screen.getByText('2개의 댓글')).toBeInTheDocument();
  });

  it('keeps non-supported sources on Coming Soon', () => {
    render(<OriginalPanel connector="github" entityType="pr" documentId="github:pr:1" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText('Github')).toBeInTheDocument();
  });
});
