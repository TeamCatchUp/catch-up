import {
  resolveDocumentBlockText,
  type WikiDocumentBlock,
  type WikiDocumentData,
  type WikiLayoutItem,
  type WikiLayoutRow,
} from '../../api/wikiDocumentMappers';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiDocumentMeta from './WikiDocumentMeta';

export interface WikiDocumentPageProps {
  document: WikiDocumentData;
  /** 채널 > 폴더 > 문서. 이름 join 결과라 문서 응답이 아니라 밖에서 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
}

/** 제목 한 줄 + 본문 한 덩이. 블록 항목과 자리표시가 같은 타이포를 쓴다 */
function DocumentSection({ heading, text }: { heading: string; text: string }) {
  return (
    <article>
      {heading.length > 0 && <h2>{heading}</h2>}
      {/* 본문의 줄바꿈이 값 표기의 구분이라 접으면 안 된다 */}
      {text.length > 0 && <p className="whitespace-pre-wrap">{text}</p>}
    </article>
  );
}

/** 여러 블록을 한 표로 묶은 항목. 표 타이포는 markdown.css의 표 규칙을 그대로 쓴다 */
function DocumentTable({ heading, rows }: { heading: string; rows: readonly WikiLayoutRow[] }) {
  return (
    <article>
      {heading.length > 0 && <h2>{heading}</h2>}
      <div className="table-wrapper">
        <table>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.label}-${index}`}>
                <th scope="row">{row.label}</th>
                <td className="whitespace-pre-wrap">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
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
    <section className="flex min-h-full flex-col">
      {/* actions 슬롯은 공급원이 없어 비워둔다 */}
      <WikiPageHeader variant="detail" breadcrumbs={breadcrumbs} onBreadcrumbClick={onBreadcrumbClick} />

      <div className="mx-auto flex w-full max-w-260 flex-1 flex-col gap-6 px-6 py-9">
        <WikiDocumentMeta title={document.title} publishedLabel={document.publishedLabel} />

        {/* 본문 타이포그래피는 공용 markdown.css를 재사용한다 — 에디터와 같은 읽기 규격이다 */}
        <div className="markdown-body">
          {/* 양식이 없는 문서 종류는 layout이 비어 오고, 그때는 blocks 순서가 표시 순서다 */}
          {document.layout.length > 0
            ? document.layout.map((item, position) => renderLayoutItem(item, position, document.blocks))
            : document.blocks.map((block) => (
                <DocumentSection
                  key={block.blockIndex}
                  heading={block.heading}
                  text={resolveDocumentBlockText(block)}
                />
              ))}
        </div>
      </div>
    </section>
  );
}
