import type { ReactNode } from 'react';

import type { DocumentBreadcrumb } from '../../types/llmWikiModel';
import type { DocumentOwner } from '../../types/llmWikiModel';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiDocumentMeta from './WikiDocumentMeta';

export interface WikiDocumentShellProps {
  title: string;
  owners: readonly DocumentOwner[];
  timeLabel: string;
  topContent?: ReactNode;
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
  owners,
  timeLabel,
  topContent,
  breadcrumbs,
  onBreadcrumbClick,
  children,
}: WikiDocumentShellProps) {
  return (
    <section className="flex min-h-full flex-col">
      {/* actions 슬롯은 공급원이 없어 비워둔다 */}
      <WikiPageHeader variant="detail" breadcrumbs={breadcrumbs} onBreadcrumbClick={onBreadcrumbClick} />

      <div className="mx-auto flex w-full max-w-260 flex-1 flex-col gap-6 px-6 pb-9 pt-8 xl:px-0">
        {topContent}
        <WikiDocumentMeta title={title} owners={owners} timeLabel={timeLabel} />

        {/* 본문 타이포그래피는 공용 markdown-reading.css 변형을 쓴다 — 에디터와 같은 읽기 규격이다 */}
        <div className="markdown-body markdown-reading">{children}</div>
      </div>
    </section>
  );
}
