import IconDashCircle from '@/public/icons/icon/dash-circle.svg';
import IconVerified from '@/public/icons/icon/verified.svg';
import { Badge } from '@/shared/components/ui/badge';

import type { DocumentStatus, KnownDocumentStatus } from '../../types/llmWikiModel';

/**
 * 시안에 실재하는 규격은 둘뿐이다.
 * - md: 문서 표의 상태 열 (100×31). 대시보드·채널 메인·폴더 메인이 쓴다
 * - sm: 태그 (h24). 검토큐 문서 헤더와 검토큐 상세 메타 줄이 쓴다
 */
export type DocumentStatusBadgeSize = 'md' | 'sm';

interface StatusPreset {
  label: string;
  variant: 'success' | 'violet';
  Icon: typeof IconVerified;
}

/**
 * 상태 → 라벨·색·아이콘. Figma 전수 조사(8/10)로 확인된 3종만 담는다.
 * 여기 없는 status는 배지를 렌더하지 않는다 — 임의 시각화가 승인된 디자인처럼 남는 것을 막는다.
 */
const STATUS_PRESET: Partial<Record<KnownDocumentStatus, StatusPreset>> = {
  reviewed: { label: '검토 완료', variant: 'success', Icon: IconVerified },
  pending_review: { label: '검토 대기', variant: 'violet', Icon: IconDashCircle },
  needs_review: { label: '검토 필요', variant: 'violet', Icon: IconDashCircle },
};

/**
 * 색은 shared Badge 변형이 Figma와 그대로 일치해 재사용하고(success = Accent/Green,
 * violet = Accent/Violet), 기하만 규격별로 덮는다.
 */
const SIZE_CLASS: Record<DocumentStatusBadgeSize, { badge: string; icon: string }> = {
  // radius/lg 8 · padding 4/8 · body(md)/small 15 · 아이콘 20
  md: { badge: 'text-body-small gap-2 rounded-lg px-2 py-1', icon: 'size-5 shrink-0' },
  // radius/md2 6 · padding 2/6 · body(md)/xsmall 13 · 아이콘 18
  sm: { badge: 'text-body-xsmall gap-1 rounded-md2 px-1.5 py-0.5', icon: 'size-4.5 shrink-0' },
};

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  size?: DocumentStatusBadgeSize;
}

/**
 * LLM Wiki 상태 배지 — 도메인 전체의 단일 공급원.
 *
 * 규격(size)과 의미(status)는 직교한다. 소비처가 자리에 맞는 규격을 고르고, 무엇을
 * 표시할지는 status가 정한다. 시안에 실재하는 조합은 (md, reviewed) · (md, pending_review) ·
 * (sm, needs_review) 셋이고 Storybook은 그 셋만 고정한다.
 *
 * 아이콘은 둘 다 currentColor로 정규화돼 있어 Badge의 글자색을 그대로 따라간다 —
 * 다크 모드에서 accent 색이 바뀌어도 함께 움직인다.
 */
export default function DocumentStatusBadge({ status, size = 'md' }: DocumentStatusBadgeProps) {
  const preset = STATUS_PRESET[status as KnownDocumentStatus];
  if (!preset) return null;

  const { label, variant, Icon } = preset;
  const geometry = SIZE_CLASS[size];

  return (
    <Badge variant={variant} className={geometry.badge}>
      <Icon aria-hidden className={geometry.icon} />
      {label}
    </Badge>
  );
}
