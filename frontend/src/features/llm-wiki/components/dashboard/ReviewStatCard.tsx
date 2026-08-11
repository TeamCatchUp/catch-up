import { cn } from '@/shared/utils/cn';

import type { ReviewStatCardData } from '../../types/llmWikiModel';

interface ReviewStatCardProps {
  stat: ReviewStatCardData;
}

interface StatCardTone {
  surface: string;
  count: string;
  label: string;
}

// 중립 톤. 수치와 라벨 색이 갈리는 유일한 카드다.
const NEUTRAL_TONE: StatCardTone = {
  surface: 'bg-fill-normal-strong',
  count: 'text-text-normal-neutral',
  label: 'text-text-normal-alternative',
};

/**
 * 톤은 API 데이터가 아니라 지표별로 못박힌 상수라 stat.id로 매핑한다.
 * 모르는 id는 새 색을 발명하지 않고 중립 톤으로 떨어뜨린다.
 */
const TONE_BY_STAT_ID: Record<string, StatCardTone> = {
  // 검토 대기
  'stat-pending-review': {
    surface: 'bg-accent-violet-neutral',
    count: 'text-accent-violet-default',
    label: 'text-accent-violet-default',
  },
  // 미해결 충돌
  'stat-open-contradictions': {
    surface: 'bg-accent-red-orange-lighten',
    count: 'text-accent-red-orange-default',
    label: 'text-accent-red-orange-default',
  },
  // 태그 미분류
  'stat-untagged': NEUTRAL_TONE,
  // 장기 미변경 문서
  'stat-stale-documents': {
    surface: 'bg-accent-information-lighten',
    count: 'text-accent-light-blue-default',
    label: 'text-accent-light-blue-default',
  },
};

export default function ReviewStatCard({ stat }: ReviewStatCardProps) {
  const tone = TONE_BY_STAT_ID[stat.id] ?? NEUTRAL_TONE;

  // 폭·높이를 고정하지 않는다 — 슬롯이 폭을 주고 높이는 내용물의 결과값이다.
  return (
    <div className={cn('shadow-card flex flex-col gap-2 rounded-xl px-4 py-3', tone.surface)}>
      {/* 타이포 토큰이 weight까지 들고 있어 font-*를 덧붙이지 않는다 */}
      <span className={cn('text-heading-xlarge', tone.count)}>{stat.count}</span>
      <span className={cn('text-body-small', tone.label)}>{stat.label}</span>
    </div>
  );
}
