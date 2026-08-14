import IconDashCircle from '@/public/icons/icon/dash-circle.svg';
import IconVerified from '@/public/icons/icon/verified.svg';
import { Badge } from '@/shared/components/ui/badge';

import type { DocumentStatus, KnownDocumentStatus } from '../../types/llmWikiModel';

/** md는 문서 표의 상태 열, sm은 헤더·메타 줄의 태그 규격이다. */
export type DocumentStatusBadgeSize = 'md' | 'sm';

interface StatusPreset {
  label: string;
  variant: 'success' | 'violet';
  Icon: typeof IconVerified;
}

/**
 * 상태 → 라벨·색·아이콘. 확정된 3종만 담는다.
 * 여기 없는 status는 렌더하지 않는다 — 임의 배지를 발명하지 않는다.
 */
const STATUS_PRESET: Partial<Record<KnownDocumentStatus, StatusPreset>> = {
  reviewed: { label: '검토 완료', variant: 'success', Icon: IconVerified },
  pending_review: { label: '검토 대기', variant: 'violet', Icon: IconDashCircle },
  needs_review: { label: '검토 필요', variant: 'violet', Icon: IconDashCircle },
};

/** 색은 shared Badge 변형을 그대로 쓰고, 기하만 규격별로 덮는다. */
const SIZE_CLASS: Record<DocumentStatusBadgeSize, { badge: string; icon: string }> = {
  md: { badge: 'text-body-small gap-2 rounded-lg px-2 py-1', icon: 'size-5 shrink-0' },
  sm: { badge: 'text-body-xsmall gap-1 rounded-md2 px-1.5 py-0.5', icon: 'size-4.5 shrink-0' },
};

/** 라벨 단일 공급원. 배지 밖(필터 칩 등)에서 같은 문자열이 필요할 때 쓴다. */
export function getDocumentStatusLabel(status: DocumentStatus): string | undefined {
  return STATUS_PRESET[status as KnownDocumentStatus]?.label;
}

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  size?: DocumentStatusBadgeSize;
}

/**
 * LLM Wiki 상태 배지 — 도메인 전체의 단일 공급원. 규격(size)과 의미(status)는 직교한다.
 * 미지 status는 렌더하지 않는다.
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
