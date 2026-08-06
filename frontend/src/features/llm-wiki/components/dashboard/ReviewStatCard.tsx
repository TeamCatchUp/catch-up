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

// 중립 톤(태그 미분류, 17600:149365). 수치와 라벨 색이 갈리는 유일한 카드다.
const NEUTRAL_TONE: StatCardTone = {
  surface: 'bg-fill-normal-strong',
  count: 'text-text-normal-neutral',
  label: 'text-text-normal-alternative',
};

/**
 * 톤은 API 데이터가 아니라 Figma가 지표별로 못박은 상수다(17600:149373 4종).
 * 그래서 타입에 tone 필드를 넣지 않고 stat.id로 매핑한다.
 * 모르는 id는 새 색을 발명하지 않고 중립 톤으로 떨어뜨린다.
 */
const TONE_BY_STAT_ID: Record<string, StatCardTone> = {
  // 검토 대기 (17600:149361)
  'stat-pending-review': {
    surface: 'bg-accent-violet-neutral',
    count: 'text-accent-violet-default',
    label: 'text-accent-violet-default',
  },
  // 미해결 충돌 (17600:149358)
  'stat-open-contradictions': {
    surface: 'bg-accent-red-orange-lighten',
    count: 'text-accent-red-orange-default',
    label: 'text-accent-red-orange-default',
  },
  // 태그 미분류 (17600:149365)
  'stat-untagged': NEUTRAL_TONE,
  // 장기 미변경 문서 (17600:149369)
  'stat-stale-documents': {
    surface: 'bg-accent-information-lighten',
    count: 'text-accent-light-blue-default',
    label: 'text-accent-light-blue-default',
  },
};

export default function ReviewStatCard({ stat }: ReviewStatCardProps) {
  const tone = TONE_BY_STAT_ID[stat.id] ?? NEUTRAL_TONE;

  // 폭은 고정하지 않는다 — Figma 카드가 horizontal fill이라 대시보드 4열이 슬롯을 나눠 갖는다.
  // 높이 87도 결과값(py 12 + 32 + gap 8 + 23 + py 12)이라 h-*로 못박지 않는다.
  return (
    <div className={cn('shadow-card flex flex-col gap-2 rounded-xl px-4 py-3', tone.surface)}>
      {/* text-heading-xlarge·text-body-small 토큰이 weight까지 들고 있어 font-*를 덧붙이지 않는다 */}
      <span className={cn('text-heading-xlarge', tone.count)}>{stat.count}</span>
      <span className={cn('text-body-small', tone.label)}>{stat.label}</span>
    </div>
  );
}
