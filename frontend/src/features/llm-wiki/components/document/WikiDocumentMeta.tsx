export interface WikiDocumentMetaProps {
  title: string;
  /** 제목 아래 한 줄. 발행 시각 표시("3시간 전")이거나 미리보기 표기다 */
  caption: string;
}

/**
 * 문서 본문 안의 메타 영역 — 제목·발행 시각. 브레드크럼 페이지 헤더와는 다른 층위다.
 * 시안의 작성자·아바타 그룹·유형/상태 태그는 표기 시안이 서지 않아 넣지 않았다.
 */
export default function WikiDocumentMeta({ title, caption }: WikiDocumentMetaProps) {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-heading-large text-text-normal-normal min-w-0 wrap-break-word">{title}</h1>
      <p className="text-body-small text-text-normal-alternative">{caption}</p>
    </div>
  );
}
