import IconVerified from '@/public/icons/icon/verified.svg';
import { Badge } from '@/shared/components/ui/badge';

import type { DocumentStatus } from '../../types/llmWikiModel';

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
}

// 디자인 확정 배지는 "검토 완료" 1종. 그 외 status는 렌더하지 않는다(임의 배지 발명 금지).
export default function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  if (status !== 'reviewed') return null;

  // 색은 shared Badge의 success 변형을 그대로 쓰고, 반경·패딩·본문 크기만 이 배지 값으로 덮는다.
  // 아이콘은 fill="currentColor"라 Badge의 글자색을 그대로 따라간다.
  return (
    <Badge variant="success" className="text-body-small gap-2 rounded-lg px-2 py-1">
      <IconVerified aria-hidden className="size-5 shrink-0" />
      검토 완료
    </Badge>
  );
}
