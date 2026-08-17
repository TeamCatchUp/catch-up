import IconDivider from '@/public/icons/icon/divider.svg';
import IconList from '@/public/icons/icon/list.svg';

import type { SlashItem } from '../../types/llmWikiEditor';
import {
  IconCallout,
  IconCheckbox,
  IconCode,
  IconHeading1,
  IconHeading2,
  IconHeading3,
  IconOrderedList,
  IconQuote,
  IconTable,
} from './editorIcons';

/**
 * 슬래시 메뉴 항목(블록 11종).
 * 아이콘은 공용 자산이 있으면 그걸 쓰고, 없으면 editorIcons의 임시 세트를 쓴다.
 */
export const SLASH_ITEMS: readonly SlashItem[] = [
  {
    id: 'heading-1',
    group: '텍스트',
    label: '제목 1',
    description: '큰 섹션 제목',
    keywords: ['제목', '헤딩', 'heading', 'h1', 'title'],
    Icon: IconHeading1,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setNode('heading', { level: 1 }).run();
    },
  },
  {
    id: 'heading-2',
    group: '텍스트',
    label: '제목 2',
    description: '중간 섹션 제목',
    keywords: ['제목', '헤딩', 'heading', 'h2'],
    Icon: IconHeading2,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setNode('heading', { level: 2 }).run();
    },
  },
  {
    id: 'heading-3',
    group: '텍스트',
    label: '제목 3',
    description: '작은 섹션 제목',
    keywords: ['제목', '헤딩', 'heading', 'h3'],
    Icon: IconHeading3,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setNode('heading', { level: 3 }).run();
    },
  },
  {
    id: 'bullet-list',
    group: '목록',
    label: '글머리 목록',
    description: '순서 없는 목록',
    // description은 필터 대상이 아니므로 '순서'를 keywords에 직접 넣는다
    keywords: ['목록', '리스트', '불릿', '순서', 'list', 'bullet', 'ul'],
    Icon: IconList,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleBulletList().run();
    },
  },
  {
    id: 'ordered-list',
    group: '목록',
    label: '번호 목록',
    description: '순서 있는 목록',
    keywords: ['목록', '번호', '리스트', '순서', 'list', 'ordered', 'ol', 'number'],
    Icon: IconOrderedList,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleOrderedList().run();
    },
  },
  {
    id: 'task-list',
    group: '목록',
    label: '체크박스',
    description: '할 일 목록',
    keywords: ['체크박스', '할일', '투두', '체크', 'todo', 'task', 'checkbox', 'check'],
    Icon: IconCheckbox,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleTaskList().run();
    },
  },
  {
    id: 'table',
    group: '블록',
    label: '표',
    description: '3×3 표 삽입',
    keywords: ['표', '테이블', 'table', 'grid'],
    Icon: IconTable,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
    },
  },
  {
    id: 'callout',
    group: '블록',
    label: '콜아웃',
    description: '강조 상자',
    keywords: ['콜아웃', '강조', '알림', 'callout', 'note', 'info'],
    Icon: IconCallout,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleCallout().run();
    },
  },
  {
    id: 'code-block',
    group: '블록',
    label: '코드',
    description: '코드 블록',
    keywords: ['코드', '소스', 'code', 'snippet'],
    Icon: IconCode,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleCodeBlock().run();
    },
  },
  {
    id: 'blockquote',
    group: '블록',
    label: '인용',
    description: '인용문',
    keywords: ['인용', '따옴표', 'quote', 'blockquote'],
    Icon: IconQuote,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleBlockquote().run();
    },
  },
  {
    id: 'horizontal-rule',
    group: '블록',
    label: '구분선',
    description: '가로 구분선',
    keywords: ['구분선', '구분', '선', 'divider', 'hr', 'rule'],
    Icon: IconDivider,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setHorizontalRule().run();
    },
  },
];

/**
 * 슬래시 메뉴 필터. cmdk 내장 필터는 보이는 검색창을 요구하고 한글 퍼지 매칭이 예측되지 않아 쓰지 않는다.
 * 항목 수가 적어 부분 문자열 일치로 충분하다.
 */
export function filterSlashItems(items: readonly SlashItem[], query: string): readonly SlashItem[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return items;

  return items.filter((item) => {
    const haystack = [item.label, ...item.keywords].join(' ').toLowerCase();
    return haystack.includes(needle);
  });
}
