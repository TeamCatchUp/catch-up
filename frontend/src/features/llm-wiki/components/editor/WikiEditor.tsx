'use client';

import { EditorContent, type JSONContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

export interface WikiEditorProps {
  /** 최초 1회만 반영된다. 이후 변경은 무시 — uncontrolled다. */
  initialContent?: JSONContent;
  editable?: boolean;
  onUpdate?: (doc: JSONContent) => void;
  onContentError?: (error: Error) => void;
}

export default function WikiEditor({ initialContent, editable = true, onUpdate, onContentError }: WikiEditorProps) {
  const editor = useEditor({
    extensions: [StarterKit],
    content: initialContent,
    editable,
    // App Router는 서버에서 한 번 렌더된다. 즉시 렌더하면 hydration이 어긋난다.
    immediatelyRender: false,
    // 켜지 않으면 ProseMirror가 스키마에 없는 노드를 말없이 버린다.
    // 지금은 픽스처만 넣어 티가 안 나지만, blocks[]가 들어올 때 claim_section이
    // 사라지고도 화면은 멀쩡해 보인다.
    enableContentCheck: true,
    onContentError: ({ error }) => {
      console.error('[WikiEditor] 스키마에 없는 콘텐츠', error);
      onContentError?.(error);
    },
    onUpdate: ({ editor: instance }) => {
      onUpdate?.(instance.getJSON());
    },
  });

  return <EditorContent editor={editor} className="min-h-40" />;
}
