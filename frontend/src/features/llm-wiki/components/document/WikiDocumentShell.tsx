import type { ReactNode } from 'react';

import type { WikiLayoutRow } from '../../api/wikiDocumentMappers';
import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiDocumentMeta from './WikiDocumentMeta';

/** 제목 한 줄 + 본문 한 덩이. 블록 항목과 자리표시가 같은 타이포를 쓴다 */
export function DocumentSection({ heading, text }: { heading: string; text: string }) {
  return (
    <article>
      {heading.length > 0 && <h2>{heading}</h2>}
      {/* 본문의 줄바꿈이 값 표기의 구분이라 접으면 안 된다 */}
      {text.length > 0 && <p className="whitespace-pre-wrap">{text}</p>}
    </article>
  );
}

/** 여러 블록을 한 표로 묶은 항목. 표 타이포는 markdown-reading.css의 표 규칙을 그대로 쓴다 */
export function DocumentTable({ heading, rows }: { heading: string; rows: readonly WikiLayoutRow[] }) {
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

export interface WikiDocumentShellProps {
  title: string;
  /** 제목 아래 한 줄. 발행 시각이거나 미리보기 표기다 */
  caption: string;
  /** 채널 > 폴더 > 문서. 이름 join 결과라 문서 응답이 아니라 밖에서 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
  /** 본문 항목들. 공용 읽기 규격(markdown-reading.css) 안에 그대로 실린다 */
  children: ReactNode;
}

/**
 * 문서 읽기 화면의 껍데기 — 경로 헤더·제목 메타·본문 폭.
 * 발행판과 제안본 미리보기가 같은 규격을 써야 해서 한자리에 둔다.
 */
export default function WikiDocumentShell({
  title,
  caption,
  breadcrumbs,
  onBreadcrumbClick,
  children,
}: WikiDocumentShellProps) {
  return (
    <section className="flex min-h-full flex-col">
      {/* actions 슬롯은 공급원이 없어 비워둔다 */}
      <WikiPageHeader variant="detail" breadcrumbs={breadcrumbs} onBreadcrumbClick={onBreadcrumbClick} />

      <div className="mx-auto flex w-full max-w-260 flex-1 flex-col gap-6 px-6 py-9">
        <WikiDocumentMeta title={title} caption={caption} />

        {/* 본문 타이포그래피는 공용 markdown-reading.css 변형을 쓴다 — 에디터와 같은 읽기 규격이다 */}
        <div className="markdown-body markdown-reading">{children}</div>
      </div>
    </section>
  );
}
