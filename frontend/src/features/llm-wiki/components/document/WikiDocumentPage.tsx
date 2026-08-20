import { resolveDocumentBlockText, type WikiDocumentData } from '../../api/wikiDocumentMappers';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiDocumentMeta from './WikiDocumentMeta';

export interface WikiDocumentPageProps {
  document: WikiDocumentData;
  /** 채널 > 폴더 > 문서. 이름 join 결과라 문서 응답이 아니라 밖에서 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
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
          {document.blocks.map((block) => {
            const text = resolveDocumentBlockText(block);

            return (
              <article key={block.blockIndex}>
                {block.heading.length > 0 && <h2>{block.heading}</h2>}
                {/* 본문의 줄바꿈이 값 표기의 구분이라 접으면 안 된다 */}
                {text.length > 0 && <p className="whitespace-pre-wrap">{text}</p>}
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
