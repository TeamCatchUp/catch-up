import type { ReactNode } from 'react';

export interface WikiDocumentMetaProps {
  title: string;
  authorName: string;
  createdLabel: string;
  /** 제목 우측 슬롯 */
  children?: ReactNode;
}

/**
 * 문서 본문 안의 메타 영역 — 제목·작성정보. 브레드크럼 페이지 헤더와는 다른 층위다.
 * 시안의 아바타 그룹·유형/상태 태그는 채울 데이터가 없어 넣지 않았다.
 */
export default function WikiDocumentMeta({ title, authorName, createdLabel, children }: WikiDocumentMetaProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-4">
        <h1 className="text-heading-large text-text-normal-normal min-w-0 flex-1 wrap-break-word">{title}</h1>
        {children}
      </div>
      <p className="text-body-small text-text-normal-alternative">
        {createdLabel} · {authorName}
      </p>
    </div>
  );
}
