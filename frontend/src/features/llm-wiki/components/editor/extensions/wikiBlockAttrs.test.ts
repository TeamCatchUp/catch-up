import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { describe, expect, it } from 'vitest';

import { WIKI_EDITOR_EXTENSIONS } from '../WikiEditor';
import { WikiBlockAttrs } from './wikiBlockAttrs';

function createEditor() {
  return new Editor({ extensions: [StarterKit, WikiBlockAttrs] });
}

describe('wikiBlockAttrs', () => {
  it('origin·claimIds는 왕복에서 살아남는다', () => {
    const editor = createEditor();
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          attrs: { origin: 'system', claimIds: ['c_1', 'c_2'] },
          content: [{ type: 'text', text: '결제 실패가 증가했다.' }],
        },
      ],
    });

    const first = editor.getJSON().content?.[0];
    expect(first?.attrs).toMatchObject({ origin: 'system', claimIds: ['c_1', 'c_2'] });
  });

  it('서버 블록 필드 5종이 왕복에서 살아남는다 — 판정 요청에 필요한 값들이다', () => {
    const editor = createEditor();
    const variants = [{ claimId: 'c_9', statement: '환불 기한은 7일', observedAt: '2026-08-01T00:00:00Z' }];
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          attrs: {
            origin: 'system',
            claimIds: ['c_1'],
            blockIndex: 3,
            blockContentHash: 'sha256:abc123',
            proposalIds: ['p_1'],
            ontologyVersion: 'v7',
            variants,
          },
          content: [{ type: 'text', text: '본문' }],
        },
      ],
    });

    expect(editor.getJSON().content?.[0]?.attrs).toMatchObject({
      blockIndex: 3,
      blockContentHash: 'sha256:abc123',
      proposalIds: ['p_1'],
      ontologyVersion: 'v7',
      variants,
    });
  });

  it('variants의 null과 빈 배열이 구별된다 — 백엔드가 둘을 다른 뜻으로 쓴다', () => {
    const editor = createEditor();
    editor.commands.setContent({
      type: 'doc',
      content: [
        { type: 'paragraph', attrs: { variants: null }, content: [{ type: 'text', text: '후보 없음' }] },
        { type: 'paragraph', attrs: { variants: [] }, content: [{ type: 'text', text: '다투는데 후보 빔' }] },
      ],
    });

    const [none, empty] = editor.getJSON().content ?? [];
    expect(none?.attrs?.variants).toBeNull();
    expect(empty?.attrs?.variants).toEqual([]);
  });

  it('blockContentHash가 DOM에 새어나가지 않는다 — 감사 증거이지 렌더용이 아니다', () => {
    const editor = createEditor();
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          attrs: { blockContentHash: 'sha256:leak-check', blockIndex: 0 },
          content: [{ type: 'text', text: '본문' }],
        },
      ],
    });

    expect(editor.getHTML()).not.toContain('sha256:leak-check');
    expect(editor.getHTML()).not.toContain('blockIndex');
  });

  it('heading에서도 보존된다 — 특정 노드만 뚫려 있으면 안 된다', () => {
    const editor = createEditor();
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'heading',
          attrs: { level: 2, origin: 'system', claimIds: ['c_9'] },
          content: [{ type: 'text', text: '현황' }],
        },
      ],
    });

    const first = editor.getJSON().content?.[0];
    expect(first?.attrs).toMatchObject({ level: 2, origin: 'system', claimIds: ['c_9'] });
  });

  it('값이 없으면 null이다 — 없는 키를 지어내지 않는다', () => {
    const editor = createEditor();
    editor.commands.setContent({
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: '검토자 메모' }] }],
    });

    const first = editor.getJSON().content?.[0];
    expect(first?.attrs).toMatchObject({ origin: null, claimIds: null });
  });

  it('DOM에는 새어나오지 않는다 — 렌더용 값이 아니다', () => {
    const editor = createEditor();
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          attrs: { origin: 'system', claimIds: ['c_1'] },
          content: [{ type: 'text', text: '본문' }],
        },
      ],
    });

    expect(editor.getHTML()).not.toContain('origin');
    expect(editor.getHTML()).not.toContain('claimIds');
    expect(editor.getHTML()).not.toContain('c_1');
  });

  it('WikiEditor의 실제 확장 목록으로도 왕복이 성립한다 — 배선 회귀 방지', () => {
    const editor = new Editor({ extensions: WIKI_EDITOR_EXTENSIONS });
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          attrs: { origin: 'system', claimIds: ['c_1'] },
          content: [{ type: 'text', text: '본문' }],
        },
      ],
    });

    expect(editor.getJSON().content?.[0]?.attrs).toMatchObject({ origin: 'system', claimIds: ['c_1'] });
  });

  it('2차 블록(체크박스·표·콜아웃)에서도 attrs·id가 보존된다 — 확장 목록과 attr 목록의 동기화 감시', () => {
    const editor = new Editor({ extensions: WIKI_EDITOR_EXTENSIONS });
    editor.commands.setContent({
      type: 'doc',
      content: [
        {
          type: 'taskList',
          attrs: { origin: 'human', claimIds: null },
          content: [
            {
              type: 'taskItem',
              attrs: { checked: false, origin: 'human', claimIds: null },
              content: [{ type: 'paragraph', content: [{ type: 'text', text: '할 일' }] }],
            },
          ],
        },
        {
          type: 'callout',
          attrs: { origin: 'system', claimIds: ['c_9'] },
          content: [{ type: 'paragraph', content: [{ type: 'text', text: '강조' }] }],
        },
      ],
    });

    const [task, callout] = editor.getJSON().content ?? [];
    expect(task?.attrs).toMatchObject({ origin: 'human' });
    expect(task?.attrs?.id).toBeTruthy();
    expect(callout?.attrs).toMatchObject({ origin: 'system', claimIds: ['c_9'] });
    expect(callout?.attrs?.id).toBeTruthy();
  });

  it('블록에 안정 ID가 자동으로 붙는다 — UniqueID 배선 회귀 방지 (스펙 §2)', () => {
    const editor = new Editor({ extensions: WIKI_EDITOR_EXTENSIONS });
    editor.commands.setContent({
      type: 'doc',
      content: [
        { type: 'paragraph', content: [{ type: 'text', text: '첫 블록' }] },
        { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: '둘째 블록' }] },
      ],
    });

    const blocks = editor.getJSON().content ?? [];
    const ids = blocks.map((node) => node.attrs?.id as string | undefined);
    expect(ids[0]).toBeTruthy();
    expect(ids[1]).toBeTruthy();
    expect(ids[0]).not.toBe(ids[1]);
  });
});
