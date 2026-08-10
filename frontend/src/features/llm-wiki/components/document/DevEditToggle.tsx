'use client';

import Link from 'next/link';

export interface DevEditToggleProps {
  documentId: string;
  /** 이 문서에 달린 픽스처 제안 id */
  proposalId: string;
  isEditing: boolean;
}

/**
 * ★ 임시 — 개발용 편집 진입점. 시안에 없는 UI다.
 *
 * 제거 조건: 검토 큐 화면이 생겨 실제 `?proposalId=` 진입이 가능해지면 이 파일을 지운다.
 * 그때 WikiDocumentPage에서 import 한 줄만 빼면 된다 — 게이트 로직은 손댈 필요가 없다.
 *
 * 게이트를 우회하지 않는다. 픽스처 제안 id를 URL에 넣어 "큐에서 넘어온 상황"을 흉내낼 뿐이라,
 * 제품 경로와 개발 경로가 같은 resolveDocumentView를 탄다. 우회 코드 경로 자체가 생기지 않는다.
 *
 * 시각도 임시임이 드러나게 둔다(DEV 라벨 + 점선). 디자인 토큰으로 예쁘게 만들면
 * 승인된 UI로 오인되는데, 그게 상태 감사 계약이 막으려는 실패다.
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
