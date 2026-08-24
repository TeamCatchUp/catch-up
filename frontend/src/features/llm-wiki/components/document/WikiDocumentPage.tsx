import {
  resolveDocumentBlockText,
  type WikiDocumentBlock,
  type WikiDocumentData,
  type WikiLayoutItem,
} from '../../api/wikiDocumentMappers';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import WikiDocumentShell, { DocumentSection, DocumentTable } from './WikiDocumentShell';

export interface WikiDocumentPageProps {
  document: WikiDocumentData;
  /** 채널 > 폴더 > 문서. 이름 join 결과라 문서 응답이 아니라 밖에서 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
}

/** 항목이 가리키는 블록이 없으면 낼 본문이 없어 건너뛴다 */
function renderLayoutItem(item: WikiLayoutItem, position: number, blocks: readonly WikiDocumentBlock[]) {
  if (item.kind === 'table') {
    return <DocumentTable key={`table-${position}`} heading={item.heading} rows={item.rows} />;
  }
  if (item.kind === 'placeholder') {
    return <DocumentSection key={`placeholder-${position}`} heading={item.heading} text={item.text} />;
  }

  const block = blocks[item.blockIndex];
  if (!block) return null;

  return (
    <DocumentSection key={`block-${item.blockIndex}`} heading={item.heading} text={resolveDocumentBlockText(block)} />
  );
}

/**
 * 문서 열람 화면. 발행판 블록을 읽기만 하고 편집·저장 경로를 두지 않는다.
 * 블록의 근거(sources)는 표시 시안이 없어 렌더하지 않는다.
 */
export default function WikiDocumentPage({ document, breadcrumbs, onBreadcrumbClick }: WikiDocumentPageProps) {
  return (
    <WikiDocumentShell
      title={document.title}
      caption={document.publishedLabel}
      breadcrumbs={breadcrumbs}
      onBreadcrumbClick={onBreadcrumbClick}
    >
      {/* 양식이 없는 문서 종류는 layout이 비어 오고, 그때는 blocks 순서가 표시 순서다 */}
      {document.layout.length > 0
        ? document.layout.map((item, position) => renderLayoutItem(item, position, document.blocks))
        : document.blocks.map((block) => (
            <DocumentSection key={block.blockIndex} heading={block.heading} text={resolveDocumentBlockText(block)} />
          ))}
    </WikiDocumentShell>
  );
}
