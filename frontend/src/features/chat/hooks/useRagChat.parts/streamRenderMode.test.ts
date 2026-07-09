import { describe, expect, it } from 'vitest';

import type { StreamEvent } from '@/features/chat/types';

import { normalizeStreamEventsForRenderMode } from './streamRenderMode';

const token = (value: string, sessionId = 'session-1'): StreamEvent => ({
  type: 'token',
  session_id: sessionId,
  token: value,
});

const processEvent = (node = 'supervisor'): StreamEvent => ({
  type: 'process',
  session_id: 'session-1',
  node,
  status: 'completed',
  reasoning: null,
  content: null,
});

const sourcesEvent = (): StreamEvent => ({
  type: 'sources',
  session_id: 'session-1',
  sources: [],
});

describe('normalizeStreamEventsForRenderMode', () => {
  it('instant replay는 연속 token 이벤트를 한 번에 렌더링할 수 있게 합친다', () => {
    const events = [processEvent(), token('안'), token('녕'), token('하세요'), sourcesEvent()];

    const normalized = normalizeStreamEventsForRenderMode(events, 'instant');

    expect(normalized).toEqual([processEvent(), token('안녕하세요'), sourcesEvent()]);
  });

  it('instant replay도 process/source 경계 너머로 token을 합치지 않는다', () => {
    const events = [token('A'), processEvent('tool_executor'), token('B')];

    const normalized = normalizeStreamEventsForRenderMode(events, 'instant');

    expect(normalized).toEqual([token('A'), processEvent('tool_executor'), token('B')]);
  });

  it('instant replay는 다른 session_id의 token을 합치지 않는다', () => {
    const events = [token('A', 'session-1'), token('B', 'session-2')];

    const normalized = normalizeStreamEventsForRenderMode(events, 'instant');

    expect(normalized).toEqual(events);
  });

  it('realtime은 token 이벤트 경계를 그대로 보존한다', () => {
    const events = [processEvent(), token('안'), token('녕'), sourcesEvent()];

    const normalized = normalizeStreamEventsForRenderMode(events, 'realtime');

    expect(normalized).toEqual(events);
    expect(normalized).not.toBe(events);
  });
});
