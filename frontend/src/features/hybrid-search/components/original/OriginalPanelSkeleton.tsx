'use client';

// 원문 패널 로딩 스켈레톤 — 상담정보 카드 + 고객정보 카드 + 메시지 영역의 대략적 배치.
// 실제 OriginalPanelContent 와 동일한 외곽(gap-3 px-6 py-4) · rounded-xl 카드 · 좌측 avatar 패턴.

import { Skeleton } from '@/shared/components/ui/skeleton';

// 메시지별 본문 라인 수 — 자연스러운 길이 변화로 로딩 흐름 흉내.
const MESSAGE_LINES = [2, 1, 3, 2] as const;

export default function OriginalPanelSkeleton() {
  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-3 px-6 py-4">
      {/* 상담 정보 카드 — 담당자 / 상담 태그 / 상담 설명 3행 */}
      <div className="bg-fill-strong border-edge-neutral flex flex-col gap-3 rounded-xl border px-5 py-4">
        <div className="flex items-center gap-10">
          <Skeleton className="h-5 w-25" />
          <Skeleton className="size-6.25 shrink-0 rounded-full" />
          <Skeleton className="h-5 w-30" />
        </div>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-5 w-25" />
          <div className="flex gap-1.5">
            <Skeleton className="rounded-md2 h-6 w-12" />
            <Skeleton className="rounded-md2 h-6 w-14" />
            <Skeleton className="rounded-md2 h-6 w-10" />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-5 w-25" />
          <Skeleton className="h-5 w-full" />
        </div>
      </div>

      {/* 고객 정보 카드 — 헤더(아이콘+라벨+chevron) + 4행(이름/이메일/전화번호/유선번호) */}
      <div className="bg-fill-strong border-edge-neutral flex flex-col rounded-xl border px-5">
        <div className="flex items-center gap-4 py-4">
          <Skeleton className="size-5.5 shrink-0" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="ml-auto size-4.5 shrink-0" />
        </div>
        <div className="flex flex-col gap-3 pb-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-10">
              <Skeleton className="h-5 w-25" />
              <Skeleton className="h-5 w-40" />
            </div>
          ))}
        </div>
      </div>

      {/* 메시지 영역 — DateIndicator + 좌측 avatar(rounded-lg) + 본문 */}
      <div className="flex min-h-0 flex-1 flex-col gap-2 pt-2">
        <Skeleton className="mx-auto h-6 w-20 rounded-full" />
        {MESSAGE_LINES.map((lines, i) => (
          <div key={i} className="flex w-full gap-3 px-3 py-3">
            <Skeleton className="size-8 shrink-0 rounded-lg" />
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <Skeleton className="h-4 w-20" />
              {Array.from({ length: lines }).map((_, lineIndex) => (
                <Skeleton key={lineIndex} className="h-4 w-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
