import { formatRelativeTime } from '@/shared/utils/formatDate';

import {
  resolveDocumentBlockText,
  type WikiDocumentBlock,
  type WikiDocumentData,
  type WikiLayoutItem,
} from '../../api/wikiDocumentMappers';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import { composeDocumentPresentation, type DocumentPresentationBlock } from './composeDocumentPresentation';
import DocumentPresentation from './DocumentPresentation';
import WikiDocumentShell from './WikiDocumentShell';

export interface WikiDocumentPageProps {
  document: WikiDocumentData;
  /** 채널 > 폴더 > 문서. 이름 join 결과라 문서 응답이 아니라 밖에서 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
}

function documentPresentationBlocks(
  blocks: readonly WikiDocumentBlock[],
  layout: readonly WikiLayoutItem[],
): DocumentPresentationBlock[] {
  if (layout.length === 0) {
    return blocks.map((block) => ({
      blockIndex: block.blockIndex,
      kind: block.kind,
      heading: block.heading,
      text: resolveDocumentBlockText(block),
    }));
  }

  return layout.flatMap((item) => {
    if (item.kind === 'placeholder') return [{ blockIndex: -1, kind: 'placeholder', heading: item.heading, text: item.text }];
    const block = blocks[item.blockIndex];
    return block
      ? [{ blockIndex: block.blockIndex, kind: block.kind, heading: item.heading, text: resolveDocumentBlockText(block) }]
      : [];
  });
}

/**
 * 문서 열람 화면. 발행판 블록을 읽기만 하고 편집·저장 경로를 두지 않는다.
 * 블록의 근거(sources)는 표시 시안이 없어 렌더하지 않는다.
 */
export default function WikiDocumentPage({ document, breadcrumbs, onBreadcrumbClick }: WikiDocumentPageProps) {
  const items = composeDocumentPresentation(documentPresentationBlocks(document.blocks, document.layout));
  const timeLabel = formatRelativeTime(document.lastEditedAt ?? document.publishedAt);

  return (
    <WikiDocumentShell
      title={document.title}
      owners={document.owners}
      timeLabel={timeLabel}
      breadcrumbs={breadcrumbs}
      onBreadcrumbClick={onBreadcrumbClick}
    >
      <DocumentPresentation items={items} />
    </WikiDocumentShell>
  );
}
