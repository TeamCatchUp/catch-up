import IconDivider from '@/public/icons/icon/divider.svg';
import IconList from '@/public/icons/icon/list.svg';

import type { SlashItem } from '../../types/llmWikiEditor';

/**
 * 골격 단계의 슬래시 항목. 전부 StarterKit이 이미 주는 블록이다.
 * 표·체크박스·콜아웃은 다음 단계다(TableKit·ListKit·커스텀 노드).
 *
 * Icon이 없는 항목은 라벨만 렌더된다 — public/icons/icon/ 에 자산이 없다.
 * 비슷한 아이콘으로 대체하지 않는다.
 */
export const SLASH_ITEMS: readonly SlashItem[] = [
  {
    id: 'heading-1',
    label: '제목 1',
    description: '큰 섹션 제목',
    keywords: ['제목', '헤딩', 'heading', 'h1', 'title'],
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setNode('heading', { level: 1 }).run();
    },
  },
  {
    id: 'heading-2',
    label: '제목 2',
    description: '중간 섹션 제목',
    keywords: ['제목', '헤딩', 'heading', 'h2'],
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setNode('heading', { level: 2 }).run();
    },
  },
  {
    id: 'heading-3',
    label: '제목 3',
    description: '작은 섹션 제목',
    keywords: ['제목', '헤딩', 'heading', 'h3'],
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).setNode('heading', { level: 3 }).run();
    },
  },
  {
    id: 'bullet-list',
    label: '글머리 목록',
    description: '순서 없는 목록',
    // description("순서 없는 목록")은 필터 대상이 아니므로 '순서'를 keywords에 직접 넣는다
    keywords: ['목록', '리스트', '불릿', '순서', 'list', 'bullet', 'ul'],
    Icon: IconList,
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleBulletList().run();
    },
  },
  {
    id: 'ordered-list',
    label: '번호 목록',
    description: '순서 있는 목록',
    keywords: ['목록', '번호', '리스트', '순서', 'list', 'ordered', 'ol', 'number'],
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleOrderedList().run();
    },
  },
  {
    id: 'code-block',
    label: '코드',
    description: '코드 블록',
    keywords: ['코드', '소스', 'code', 'snippet'],
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleCodeBlock().run();
    },
  },
  {
    id: 'blockquote',
    label: '인용',
    description: '인용문',
    keywords: ['인용', '따옴표', 'quote', 'blockquote'],
    command: (editor, range) => {
      editor.chain().focus().deleteRange(range).toggleBlockquote().run();
    },
  },
  {
    id: 'horizontal-rule',
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
 * 슬래시 메뉴 필터.
 *
 * cmdk 내장 필터(command-score)를 쓰지 않는다. 두 가지 이유다.
 * 1. cmdk는 Command.Input 없이 검색 상태를 갖지 못하는데, 공용 래퍼의 CommandInput은
 *    테두리·삭제 버튼이 달린 보이는 검색창이라 슬래시 메뉴에 쓸 자리가 없다.
 * 2. command-score는 영문 퍼지 매칭 설계라 한글에서 결과가 예측되지 않는다.
 *
 * 부분 문자열 일치로 충분하다 — 항목이 8개고, 한글은 퍼지 매칭이 오히려 방해가 된다.
 */
export function filterSlashItems(items: readonly SlashItem[], query: string): readonly SlashItem[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return items;

  return items.filter((item) => {
    const haystack = [item.label, ...item.keywords].join(' ').toLowerCase();
    return haystack.includes(needle);
  });
}
