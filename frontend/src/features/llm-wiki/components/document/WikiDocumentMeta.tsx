export interface WikiDocumentMetaProps {
  title: string;
  /** 발행 시각 표시 문자열 (예: "3시간 전") */
  publishedLabel: string;
}

/**
 * 문서 본문 안의 메타 영역 — 제목·발행 시각. 브레드크럼 페이지 헤더와는 다른 층위다.
 * 시안의 작성자·아바타 그룹·유형/상태 태그는 대응 필드가 없어 넣지 않았다.
 */
export default function WikiDocumentMeta({ title, publishedLabel }: WikiDocumentMetaProps) {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-heading-large text-text-normal-normal min-w-0 wrap-break-word">{title}</h1>
      <p className="text-body-small text-text-normal-alternative">{publishedLabel}</p>
    </div>
  );
}
