'use client';

// 원문 패널 로딩 스켈레톤 — 헤더 / 상담·고객정보 / 메시지 영역의 대략적 배치를 흉내낸다.

import { Skeleton } from '@/shared/components/ui/skeleton';

// 좌/우 정렬을 번갈아 — 고객·응답자 말풍선 흐름 흉내.
const MESSAGE_ROWS = [
  { align: 'left', lines: 2 },
  { align: 'right', lines: 1 },
  { align: 'left', lines: 3 },
  { align: 'right', lines: 2 },
] as const;

export default function OriginalPanelSkeleton() {
  return (
    <div className="flex w-full flex-col">
      {/* 헤더 */}
      <div className="border-edge-neutral flex items-center gap-2 border-b px-5 py-4">
        <Skeleton className="h-5 w-1/2" />
      </div>

      {/* 상담·고객정보 */}
      <div className="border-edge-neutral flex flex-col gap-3 border-b px-5 py-4">
        <Skeleton className="h-4 w-24" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-16 rounded-full" />
          <Skeleton className="h-6 w-16 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
        <Skeleton className="h-4 w-40" />
      </div>

      {/* 메시지 영역 */}
      <div className="flex flex-col gap-6 px-5 py-6">
        <Skeleton className="mx-auto h-5 w-20 rounded-full" />
        {MESSAGE_ROWS.map((row, index) => (
          <div
            key={index}
            className={`flex w-full gap-2 ${row.align === 'right' ? 'flex-row-reverse' : ''}`}
          >
            <Skeleton className="size-8 shrink-0 rounded-full" />
            <div
              className={`flex max-w-3/4 flex-1 flex-col gap-1.5 ${
                row.align === 'right' ? 'items-end' : ''
              }`}
            >
              <Skeleton className="h-3 w-20" />
              {Array.from({ length: row.lines }).map((_, lineIndex) => (
                <Skeleton key={lineIndex} className="h-4 w-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
