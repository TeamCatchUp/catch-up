import type { SseStreamEventEnvelopeApi, StreamEventApi } from '@/features/chat/types/api/streamApi';

export const parseSSEBlock = (block: string): SseStreamEventEnvelopeApi | null => {
  const idLine = block
    .split('\n')
    .map((line) => line.trimEnd())
    .find((line) => line.startsWith('id:'));
  const id = idLine?.slice(3).trim() || undefined;

  const dataLines = block
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (dataLines.length === 0) return null;

  try {
    return {
      id,
      event: JSON.parse(dataLines.join('\n')) as StreamEventApi,
    };
  } catch {
    return null;
  }
};

export async function parseSSEStream(
  res: Response,
  onEnvelope: (envelope: SseStreamEventEnvelopeApi) => void,
): Promise<void> {
  if (!res.ok) throw new Error(`Stream error: ${res.status}`);

  if (!res.body) {
    throw new Error('Stream error: empty response body');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';

    for (const block of blocks) {
      const envelope = parseSSEBlock(block);
      if (envelope) onEnvelope(envelope);
    }

    if (done) break;
  }

  const tail = buffer.trim();
  if (tail) {
    const envelope = parseSSEBlock(tail);
    if (envelope) onEnvelope(envelope);
  }
}
