import { describe, expect, it } from 'vitest';

import type { ChatData, ChatSource, Message } from '@/features/chat/types';

import { mergeServerChatData } from './mergeServerChatData';

const buildSource = (id: string, isCited = false): ChatSource => ({
  id,
  source_type: 'github',
  entity_type: 'pr',
  is_cited: isCited,
  repo: 'org/repo',
  title: `Source ${id}`,
  content: `Content of ${id}`,
  date: '2025-01-01',
  author: 'tester',
  html_url: `https://example.com/${id}`,
  source_index: 1,
});

const buildUserMsg = (id: string, content: string): Message => ({
  id,
  role: 'user',
  content,
  timestamp: '2025-01-01T00:00:00Z',
});

const buildAssistantMsg = (id: string, content: string, sources: ChatSource[] = []): Message => ({
  id,
  role: 'assistant',
  content,
  sources,
  timestamp: '2025-01-01T00:00:00Z',
});

const buildChatData = (messages: Message[]): ChatData => ({
  session_id: 'sess-1',
  title: 'test',
  repo: '',
  messages,
});

describe('mergeServerChatData', () => {
  it('case A: 서버 sources 비어있고 streaming sources 있으면 prev sources 보존', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-user', '질문'),
      buildAssistantMsg('uuid-assistant', '답변', [buildSource('s1', true)]),
    ]);
    const serverData = buildChatData([buildUserMsg('1', '질문'), buildAssistantMsg('2', '답변', [])]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages).toHaveLength(2);
    expect(merged.messages[0].id).toBe('uuid-user');
    expect(merged.messages[1].id).toBe('uuid-assistant');
    expect(merged.messages[1].sources).toHaveLength(1);
    expect(merged.messages[1].sources?.[0].id).toBe('s1');
  });

  it('case B: 서버 sources 있으면 서버 우선', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-user', '질문'),
      buildAssistantMsg('uuid-assistant', '답변', [buildSource('streaming-s1')]),
    ]);
    const serverData = buildChatData([
      buildUserMsg('1', '질문'),
      buildAssistantMsg('2', '답변', [buildSource('server-s1', true), buildSource('server-s2', true)]),
    ]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages[1].id).toBe('uuid-assistant');
    expect(merged.messages[1].sources).toHaveLength(2);
    expect(merged.messages[1].sources?.map((s) => s.id)).toEqual(['server-s1', 'server-s2']);
  });

  it('case C: 서버에 새 entry가 있으면 그 부분만 append, 기존 id 보존', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-user', '질문1'),
      buildAssistantMsg('uuid-assistant', '답변1', [buildSource('s1')]),
    ]);
    const serverData = buildChatData([
      buildUserMsg('1', '질문1'),
      buildAssistantMsg('2', '답변1', [buildSource('s1', true)]),
      buildUserMsg('3', '질문2'),
      buildAssistantMsg('4', '답변2', [buildSource('s2', true)]),
    ]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages).toHaveLength(4);
    expect(merged.messages[0].id).toBe('uuid-user');
    expect(merged.messages[1].id).toBe('uuid-assistant');
    expect(merged.messages[2].id).toBe('3');
    expect(merged.messages[3].id).toBe('4');
  });

  it('case D: 서버 entry < prev (커밋 지연)이면 초과분 prev 보존', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-user-1', '질문1'),
      buildAssistantMsg('uuid-assistant-1', '답변1', [buildSource('s1')]),
      buildUserMsg('uuid-user-2', '질문2'),
      buildAssistantMsg('uuid-assistant-2', '답변2', []),
    ]);
    const serverData = buildChatData([
      buildUserMsg('1', '질문1'),
      buildAssistantMsg('2', '답변1', [buildSource('s1', true)]),
    ]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages).toHaveLength(4);
    expect(merged.messages[2].id).toBe('uuid-user-2');
    expect(merged.messages[3].id).toBe('uuid-assistant-2');
  });

  it('case E: content trim 차이 시 위치 매칭으로 id 보존', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-user', '질문 '),
      buildAssistantMsg('uuid-assistant', '답변\n', [buildSource('s1')]),
    ]);
    const serverData = buildChatData([buildUserMsg('1', '질문'), buildAssistantMsg('2', '답변', [])]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages[0].id).toBe('uuid-user');
    expect(merged.messages[1].id).toBe('uuid-assistant');
    expect(merged.messages[1].sources).toHaveLength(1);
  });

  it('case F: 새 user 메시지가 prev에 추가된 직후 서버 응답에 없으면 보존', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-1', 'Q1'),
      buildAssistantMsg('uuid-2', 'A1', [buildSource('s1')]),
      buildUserMsg('uuid-3', 'Q2 (방금 보낸 새 질문)'),
    ]);
    const serverData = buildChatData([
      buildUserMsg('1', 'Q1'),
      buildAssistantMsg('2', 'A1', [buildSource('s1', true)]),
    ]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages).toHaveLength(3);
    expect(merged.messages[2].id).toBe('uuid-3');
    expect(merged.messages[2].content).toBe('Q2 (방금 보낸 새 질문)');
  });

  it('스트림 종료 시 attach한 pipeline_result를 server 응답에 없어도 보존한다', () => {
    const prev = buildChatData([
      buildUserMsg('uuid-user', '질문'),
      {
        ...buildAssistantMsg('uuid-assistant', '답변', [buildSource('s1', true)]),
        pipeline_result: [{ node: 'supervisor', status: 'completed', reasoning: '분석', content: null }],
      },
    ]);
    const serverData = buildChatData([
      buildUserMsg('1', '질문'),
      buildAssistantMsg('2', '답변', [buildSource('s1', true)]),
    ]);

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages[1].id).toBe('uuid-assistant');
    expect(merged.messages[1].pipeline_result).toHaveLength(1);
    expect(merged.messages[1].pipeline_result?.[0].node).toBe('supervisor');
  });

  it('chat_history_id를 server 응답으로 patch한다', () => {
    const prev = buildChatData([buildUserMsg('uuid-user', '질문'), buildAssistantMsg('uuid-assistant', '답변')]);
    const serverData: ChatData = {
      ...buildChatData([buildUserMsg('1', '질문')]),
      messages: [buildUserMsg('1', '질문'), { ...buildAssistantMsg('2', '답변'), chat_history_id: '2' }],
    };

    const merged = mergeServerChatData(prev, serverData);

    expect(merged.messages[1].id).toBe('uuid-assistant');
    expect(merged.messages[1].chat_history_id).toBe('2');
  });
});
