export interface DocumentPresentationBlock {
  blockIndex: number;
  kind: string;
  heading: string;
  text: string;
}

export interface DocumentPresentationRow {
  heading: string;
  text: string;
}

export type DocumentPresentationItem =
  | { kind: 'summary'; heading: string; text: string }
  | { kind: 'details'; rows: readonly DocumentPresentationRow[] }
  | { kind: 'timeline'; items: readonly DocumentPresentationRow[] }
  | { kind: 'section'; heading: string; text: string };

const DETAIL_HEADINGS = new Set(['요청 배경', '요청 상태']);
const TIMELINE_HEADINGS = new Set(['사용 상황', '요청자 역할', '빈도', '지원 상태']);

export function composeDocumentPresentation(
  blocks: readonly DocumentPresentationBlock[],
): DocumentPresentationItem[] {
  const items: DocumentPresentationItem[] = [];

  for (let index = 0; index < blocks.length; ) {
    const block = blocks[index];
    const row = { heading: block.heading, text: block.text };

    if (block.kind === 'summary' && block.heading === '한 줄 요약') {
      items.push({ kind: 'summary', ...row });
      index += 1;
      continue;
    }

    if (DETAIL_HEADINGS.has(block.heading)) {
      const rows: DocumentPresentationRow[] = [];
      while (index < blocks.length && DETAIL_HEADINGS.has(blocks[index].heading)) {
        rows.push({ heading: blocks[index].heading, text: blocks[index].text });
        index += 1;
      }
      items.push({ kind: 'details', rows });
      continue;
    }

    if (TIMELINE_HEADINGS.has(block.heading)) {
      const timelineItems: DocumentPresentationRow[] = [];
      while (index < blocks.length && TIMELINE_HEADINGS.has(blocks[index].heading)) {
        timelineItems.push({ heading: blocks[index].heading, text: blocks[index].text });
        index += 1;
      }
      items.push({ kind: 'timeline', items: timelineItems });
      continue;
    }

    items.push({ kind: 'section', ...row });
    index += 1;
  }

  return items;
}
