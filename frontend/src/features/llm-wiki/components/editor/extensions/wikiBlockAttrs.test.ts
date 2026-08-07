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
