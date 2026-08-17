'use client';

import Link from 'next/link';

export interface DevEditToggleProps {
  documentId: string;
  /** 이 문서에 달린 픽스처 제안 id */
  proposalId: string;
  isEditing: boolean;
}

/**
 * 임시 개발용 편집 진입점. 시안에 없는 UI라 DEV 라벨과 점선으로 임시임을 드러낸다.
 * 검토 큐에서 실제 `?proposalId=` 진입이 가능해지면 이 파일을 지운다.
 */
export default function DevEditToggle({ documentId, proposalId, isEditing }: DevEditToggleProps) {
  const href = isEditing ? `/llm-wiki/${documentId}` : `/llm-wiki/${documentId}?proposalId=${proposalId}`;

  return (
    <Link
      href={href}
      className="text-label-small text-text-normal-alternative flex shrink-0 items-center gap-1.5 rounded-md border border-dashed border-current px-2 py-1"
    >
      <span className="text-label-xsmall rounded-sm border border-current px-1">DEV</span>
      {isEditing ? '열람으로' : '편집하기'}
    </Link>
  );
}
