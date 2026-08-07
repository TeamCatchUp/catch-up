import { Extension } from '@tiptap/core';
import { PluginKey } from '@tiptap/pm/state';
import Suggestion from '@tiptap/suggestion';
import { search } from 'node-emoji';

import type { EmojiItem, EmojiMenuState } from '../../../types/llmWikiEditor';

export interface EmojiCommandOptions {
  onStateChange: (state: EmojiMenuState | null) => void;
  onKeyDown: (event: KeyboardEvent) => boolean;
}

const MAX_RESULTS = 8;

/**
 * `:` 이모지 서제스천 브리지 — slashCommand와 같은 패턴 (스펙 §12).
 *
 * 트리거는 슬래시와 달리 노션식으로 완화하지 않는다: `http://`의 콜론에서 메뉴가 뜨면
 * URL 타이핑이 매번 방해받는다. 공백 뒤·블록 시작에서만 열고, 검색어 1자 이상일 때만
 * 항목을 준다(`:`만 쳤을 때 전체 목록이 쏟아지는 것 방지).
 */
export const EmojiCommand = Extension.create<EmojiCommandOptions>({
  name: 'emojiCommand',

  addOptions() {
    return {
      onStateChange: () => {},
      onKeyDown: () => false,
    };
  },

  addProseMirrorPlugins() {
    const { onStateChange, onKeyDown } = this.options;

    return [
      Suggestion<EmojiItem>({
        editor: this.editor,
        char: ':',
        // Suggestion 기본 pluginKey는 전역 공유다 — slashCommand와 같은 에디터에 살므로 고유 키 필수
        pluginKey: new PluginKey('emojiSuggestion'),
        allowedPrefixes: [' '],
        startOfLine: false,
        items: ({ query }) => {
          if (query.trim().length === 0) return [];
          return search(query).slice(0, MAX_RESULTS);
        },
        command: ({ editor, range, props }) => {
          editor.chain().focus().deleteRange(range).insertContent(`${props.emoji} `).run();
        },
        render: () => {
          let currentProps: {
            items: EmojiItem[];
            query: string;
            clientRect?: (() => DOMRect | null) | null;
            command: (item: EmojiItem) => void;
          } | null = null;

          const publish = () => {
            if (!currentProps || currentProps.items.length === 0) {
              onStateChange(null);
              return;
            }
            onStateChange({
              items: currentProps.items,
              query: currentProps.query,
              clientRect: currentProps.clientRect?.() ?? null,
              onSelect: currentProps.command,
            });
          };

          return {
            onStart: (props) => {
              currentProps = props;
              publish();
            },
            onUpdate: (props) => {
              currentProps = props;
              publish();
            },
            onKeyDown: ({ event }) => onKeyDown(event),
            onExit: () => {
              currentProps = null;
              publish();
            },
          };
        },
      }),
    ];
  },
});
