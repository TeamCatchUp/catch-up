import type { ReactNode } from 'react';

interface ReviewQueueListHeaderProps {
  count: number;
  /** 우측 필터 슬롯. 내용물은 소비처가 정하고 헤더는 자리만 책임진다 */
  filter?: ReactNode;
}

/** 검토 큐 좌측 목록 패널의 헤더 — 제목 + 건수 칩 + 필터 슬롯. */
export default function ReviewQueueListHeader({ count, filter }: ReviewQueueListHeaderProps) {
  return (
    <div className="border-line-normal-neutral flex h-13 shrink-0 items-center gap-5 border-b py-2 pr-2 pl-4">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <h1 className="text-heading-small text-text-normal-alternative truncate">요청된 변경사항</h1>
        <span className="bg-fill-normal-interaction-hover text-heading-small text-text-normal-alternative flex h-6 shrink-0 items-center rounded-lg px-2">
          {count}
        </span>
      </div>
      {filter}
    </div>
  );
}
