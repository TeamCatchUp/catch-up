'use client';

import { Chip } from '@/shared/components/ui/chips';

/**
 * 필터 값 4종.
 * 앞 3개는 API의 `mapping_status`(all/full/partial)와 1:1이고,
 * `channel_talk`은 표를 채널톡 1열로 좁히는 뷰 필터다 — 상태 필터가 아니라
 * 조회는 `all`로 나간다(Figma `17300:80428` 채널톡 화면).
 */
export type MappingStatusFilter = 'all' | 'full' | 'partial' | 'channel_talk';

const FILTERS: readonly { value: MappingStatusFilter; label: string }[] = [
  { value: 'all', label: '전체 이용자' },
  { value: 'full', label: '전체 연동됨' },
  { value: 'partial', label: '일부 미연동' },
  { value: 'channel_talk', label: '채널톡' },
];

interface MappingFilterChipsProps {
  value: MappingStatusFilter;
  onChange: (next: MappingStatusFilter) => void;
}

/**
 * 계정 매핑 상태 필터 칩.
 * Figma `17379:78312` 좌측 — 임베딩 히스토리 필터와 같은 낱개 칩 토글이라
 * `Chip variant="outline"`을 그대로 쓴다. 칩 마스터 라벨은 플레이스홀더(✏️ Value)라
 * 라벨은 화면 스크린샷 실측이다.
 *
 * 커넥터 칩은 채널톡 하나만 **고정**으로 둔다(사용자 결정 2026-08-04) —
 * 통계 카드는 표시 전용이라 칩을 만들지 않는다.
 */
export default function MappingFilterChips({ value, onChange }: MappingFilterChipsProps) {
  return (
    <div role="tablist" className="flex flex-wrap gap-1">
      {FILTERS.map((option) => (
        <Chip
          key={option.value}
          variant="outline"
          selected={option.value === value}
          role="tab"
          aria-selected={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </Chip>
      ))}
    </div>
  );
}
