import IconStatAllWiki from '@/public/icons/icon/stat_all_wiki.svg';
import IconStatMyAssigned from '@/public/icons/icon/stat_my_assigned.svg';
import IconStatPendingReview from '@/public/icons/icon/stat_pending_review.svg';
import IconStatUnassigned from '@/public/icons/icon/stat_unassigned.svg';

import type { ReviewStatCardData } from '../../types/llmWikiModel';

interface ReviewStatCardProps {
  stat: ReviewStatCardData;
  /** 주면 카드가 버튼이 된다 — 누르면 소비처가 아래 표에 같은 이름의 필터를 건다. */
  onClick?: (statId: string) => void;
}

/**
 * 일러스트는 API 데이터가 아니라 지표별로 못박힌 상수라 stat.id로 매핑한다.
 * 모르는 id는 그림을 발명하지 않고 회색 패널만 남긴다.
 */
const ILLUSTRATION_BY_STAT_ID: Record<string, typeof IconStatPendingReview> = {
  'stat-pending-review': IconStatPendingReview,
  'stat-my-assigned': IconStatMyAssigned,
  'stat-unassigned': IconStatUnassigned,
  'stat-all-wiki': IconStatAllWiki,
};

export default function ReviewStatCard({ stat, onClick }: ReviewStatCardProps) {
  const Illustration = ILLUSTRATION_BY_STAT_ID[stat.id];

  // 폭·높이를 고정하지 않는다 — 슬롯이 폭을 주고 높이는 내용물의 결과값이다.
  const content = (
    <>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5 px-5 py-4 text-left">
        {/* 타이포 토큰이 weight까지 들고 있어 font-*를 덧붙이지 않는다 */}
        <span className="text-body-small text-text-normal-alternative truncate">{stat.label}</span>
        <span className="text-heading-xlarge text-text-normal-normal truncate">{stat.count}</span>
      </div>
      {/* 일러스트 SVG가 같은 배경색을 품고 있어, 패널 배경은 여백 메움용이다 */}
      <div className="bg-fill-normal-strong flex w-25 shrink-0 items-center justify-center self-stretch">
        {Illustration && <Illustration aria-hidden className="h-full w-full" />}
      </div>
    </>
  );

  const shellClass = 'border-line-normal-neutral flex items-stretch overflow-clip rounded-xl border';

  // 핸들러가 없으면 버튼이 아니다 — 누를 곳처럼 보이게 두지 않는다(NavTree 정적 표시형 선례).
  // 선택된 카드의 시각은 시안에 없어 넣지 않았다 — 활성 표시는 아래 필터 칩이 맡는다.
  if (!onClick) return <div className={shellClass}>{content}</div>;

  return (
    <button
      type="button"
      onClick={() => onClick(stat.id)}
      className={`${shellClass} hover:bg-fill-normal-interaction-hover w-full cursor-pointer transition-colors`}
    >
      {content}
    </button>
  );
}
