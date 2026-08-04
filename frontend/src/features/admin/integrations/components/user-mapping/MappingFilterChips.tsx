'use client';

import { cn } from '@/shared/utils/cn';

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
 * 계정 매핑 상태 필터.
 * Figma `17379:78313` — 낱개 칩이 아니라 **세그먼티드 컨트롤**이다.
 * 트랙 `fill/normal/strong` + `line/normal/neutral` 1px + radius 8, padding·gap 2.
 * 칩 h32, padding 8/10, radius 7.
 *   미선택  배경 없음, `text/normal/alternative`
 *   선택    `fill/normal/normal` + `line/normal/assistive` 1px, `text/normal/normal`
 *
 * hover·pressed 는 임베딩 관리/현황 탭(`EmbeddingSegmentTabs`)과 같게 맞춘다
 * (사용자 지시) — Figma 토글이 두 상태를 같은 6%로 두고 있어 같은 토큰을 쓴다.
 *
 * 선택 칩에만 테두리가 있어 미선택에 투명 테두리를 깔아야 상태가 바뀔 때
 * 1px 씩 튀지 않는다.
 *
 * 커넥터 칩은 채널톡 하나만 고정이다(사용자 결정 2026-08-04) —
 * 통계 카드는 표시 전용이라 칩을 만들지 않는다.
 */
export default function MappingFilterChips({ value, onChange }: MappingFilterChipsProps) {
  return (
    <div
      role="tablist"
      className="bg-fill-normal-strong border-line-normal-neutral flex w-fit max-w-full items-center gap-0.5 overflow-x-auto rounded-lg border p-0.5"
    >
      {FILTERS.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              // radius 7 은 트랙 8에서 padding 2를 뺀 Figma 실측값이라 스케일에 없다
              'text-body-small flex h-8 shrink-0 cursor-pointer items-center rounded-[7px] border px-2.5 py-2 whitespace-nowrap transition-colors',
              selected
                ? 'bg-fill-normal-normal border-line-normal-assistive text-text-normal-normal'
                : 'text-text-normal-alternative hover:bg-fill-normal-interaction-hover active:bg-fill-normal-interaction-hover border-transparent',
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
