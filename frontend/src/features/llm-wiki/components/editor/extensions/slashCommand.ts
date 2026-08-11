import { type Editor, Extension, type Range } from '@tiptap/core';
import { PluginKey } from '@tiptap/pm/state';
import Suggestion from '@tiptap/suggestion';

import type { SlashItem, SlashMenuState } from '../../../types/llmWikiEditor';
import { filterSlashItems, SLASH_ITEMS } from '../slashItems';

export interface SlashCommandOptions {
  /** 메뉴 상태를 React로 올려보낸다. null이면 닫으라는 뜻이다. */
  onStateChange: (state: SlashMenuState | null) => void;
  /** 메뉴가 키를 소비했는지 묻는다. true면 에디터가 그 키를 먹지 않는다. */
  onKeyDown: (event: KeyboardEvent) => boolean;
}

/**
 * @tiptap/suggestion의 명령형 콜백을 React 상태로 번역하는 브리지.
 * 이 파일만 Tiptap과 메뉴 양쪽을 안다.
 */
export const SlashCommand = Extension.create<SlashCommandOptions>({
  name: 'slashCommand',

  addOptions() {
    return {
      onStateChange: () => {},
      onKeyDown: () => false,
    };
  },

  addProseMirrorPlugins() {
    const { onStateChange, onKeyDown } = this.options;

    return [
      Suggestion<SlashItem>({
        editor: this.editor,
        // emojiCommand와 같은 에디터에 산다 — 기본 pluginKey 공유 충돌 방지
        pluginKey: new PluginKey('slashSuggestion'),
        char: '/',
        // 단어 끝에 바로 /를 쳐도 연다 — "및/또는" 입력 중 메뉴가 번쩍이는 것은 감수한 동작이다.
        allowedPrefixes: null,
        startOfLine: false,
        items: ({ query }) => [...filterSlashItems(SLASH_ITEMS, query)],
        command: ({ editor, range, props }) => {
          props.command(editor as Editor, range as Range);
        },
        render: () => {
          let currentProps: {
            items: SlashItem[];
            query: string;
            clientRect?: (() => DOMRect | null) | null;
            command: (item: SlashItem) => void;
          } | null = null;

          const publish = () => {
            if (!currentProps) {
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
            // Escape는 여기서 처리하지 않는다 — Suggestion이 먼저 가로채 exit까지 수행하고, onExit이 메뉴를 닫는다.
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
