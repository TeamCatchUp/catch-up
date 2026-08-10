import type { ReactNode } from 'react';

export interface WikiDocumentMetaProps {
  title: string;
  authorName: string;
  createdLabel: string;
  /** 제목 우측 슬롯. 지금은 임시 편집 버튼, 나중에 아바타 그룹(별도 워크스트림) */
  children?: ReactNode;
}

/**
 * 문서 메타 영역 — 제목·작성정보.
 *
 * 페이지 헤더(브레드크럼 52px 바)가 아니다. Figma 실측상 둘은 다른 층위다:
 *   17735:187317 "Header" 1376×52   ← 카드 밖 = 페이지 헤더 (헤더 세션 소유)
 *   17735:187318 Card
 *     17735:187320 Horizontal        ← 카드 안 = 이 컴포넌트
 *
 * 시안에 있으나 만들지 않은 것: 아바타 그룹("12명")·유형/상태 태그.
 * 둘 다 채울 데이터가 없어 별도 워크스트림으로 분리됐다(스펙 §4).
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
