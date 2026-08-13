import IconStatMyAssigned from '@/public/icons/icon/stat_my_assigned.svg';
import IconStatPendingReview from '@/public/icons/icon/stat_pending_review.svg';
import IconStatUnassigned from '@/public/icons/icon/stat_unassigned.svg';

import type { ReviewStatCardData } from '../../types/llmWikiModel';

interface ReviewStatCardProps {
  stat: ReviewStatCardData;
}

/**
 * 일러스트는 API 데이터가 아니라 지표별로 못박힌 상수라 stat.id로 매핑한다.
 * 모르는 id는 그림을 발명하지 않고 회색 패널만 남긴다.
 */
const ILLUSTRATION_BY_STAT_ID: Record<string, typeof IconStatPendingReview> = {
  'stat-pending-review': IconStatPendingReview,
  'stat-my-assigned': IconStatMyAssigned,
  'stat-unassigned': IconStatUnassigned,
};

export default function ReviewStatCard({ stat }: ReviewStatCardProps) {
  const Illustration = ILLUSTRATION_BY_STAT_ID[stat.id];

  // 폭·높이를 고정하지 않는다 — 슬롯이 폭을 주고 높이는 내용물의 결과값이다.
  return (
    <div className="border-line-normal-neutral flex items-stretch overflow-clip rounded-xl border">
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 px-5 py-4">
        {/* 타이포 토큰이 weight까지 들고 있어 font-*를 덧붙이지 않는다 */}
        <span className="text-body-small text-text-normal-alternative truncate">{stat.label}</span>
        <span className="text-heading-xlarge text-text-normal-normal truncate">{stat.count}</span>
      </div>
      {/* 일러스트 SVG가 같은 배경색을 품고 있어, 패널 배경은 여백 메움용이다 */}
      <div className="bg-fill-normal-strong flex w-25 shrink-0 items-center justify-center self-stretch">
        {Illustration && <Illustration aria-hidden className="h-full w-full" />}
      </div>
    </div>
  );
}
