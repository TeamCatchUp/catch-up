import { describe, expect, it, vi } from 'vitest';

import { parseSSEBlock, parseSSEStream } from './streamSseParser';

describe('parseSSEBlock', () => {
  it('parses event id and JSON data', () => {
    expect(parseSSEBlock('id: 10-2\ndata: {"type":"token","token":"hi"}')).toEqual({
      id: '10-2',
      event: { type: 'token', token: 'hi' },
    });
  });

  it('parses multiline data payloads', () => {
    const block = 'id: 10-3\ndata: {"type":"token",\ndata: "token":"hi"}';
    expect(parseSSEBlock(block)).toEqual({
      id: '10-3',
      event: { type: 'token', token: 'hi' },
    });
  });

  it('returns null for malformed JSON', () => {
    expect(parseSSEBlock('id: 10-4\ndata: {')).toBeNull();
  });

  it('returns null when data is missing', () => {
    expect(parseSSEBlock('id: 10-5')).toBeNull();
  });
});

describe('parseSSEStream', () => {
  it('emits parsed envelopes from a response body', async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('id: 1-0\ndata: {"type":"token","token":"A"}\n\n'));
        controller.close();
      },
    });
    const onEnvelope = vi.fn();

    await parseSSEStream(new Response(stream, { status: 200 }), onEnvelope);

    expect(onEnvelope).toHaveBeenCalledWith({
      id: '1-0',
      event: { type: 'token', token: 'A' },
    });
  });

  it('throws on non-ok response', async () => {
    await expect(parseSSEStream(new Response('conflict', { status: 409 }), vi.fn())).rejects.toThrow(
      'Stream error: 409',
    );
  });
});
