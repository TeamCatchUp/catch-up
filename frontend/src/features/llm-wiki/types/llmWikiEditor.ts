import type { ComponentType, SVGProps } from 'react';
import type { Editor, Range } from '@tiptap/core';

/**
 * 슬래시 메뉴의 한 항목. 메뉴는 블록을 알지 못한다 — 항목이 자기가 뭘 하는지 들고 있다.
 *
 * Icon이 optional인 이유: public/icons/icon/ 에 제목·코드·인용 아이콘 자산이 없다.
 * 없는 아이콘을 비슷한 것으로 대체하지 않는다(지어낸 시각이 승인된 디자인처럼 남는다).
 * 자산 요청은 design-request에 올라가 있다.
 */
export interface SlashItem {
  id: string;
  label: string;
  description?: string;
  /** 한글·영문을 둘 다 넣는다. 사용자가 /제목도 /h1도 친다. */
  keywords: readonly string[];
  Icon?: ComponentType<SVGProps<SVGSVGElement>>;
  command: (editor: Editor, range: Range) => void;
}

/** slashCommand 확장이 React로 올려보내는 메뉴 상태. null이면 닫힘. */
export interface SlashMenuState {
  items: readonly SlashItem[];
  query: string;
  /** 커서 위치. Popover anchor를 여기로 옮긴다. */
  clientRect: DOMRect | null;
  /** 항목이 선택됐을 때 Suggestion에게 알린다. */
  onSelect: (item: SlashItem) => void;
}

/** SlashMenu가 밖으로 내주는 키보드 핸들. true를 반환하면 에디터가 그 키를 먹지 않는다. */
export interface SlashMenuHandle {
  onKeyDown: (event: KeyboardEvent) => boolean;
}
