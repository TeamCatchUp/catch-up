import { Skeleton } from '@/shared/components/ui/skeleton';

const RESOURCE_ROW_COUNT = 4;

/**
 * 우측 상세 영역의 초기 로딩 골격.
 * 연동 상태 카드 → 데이터 범위 카드 → 리소스 목록 순서로 실제 레이아웃을 따른다.
 * 텍스트를 포함하지 않는다 — 승인되지 않은 카피를 만들지 않기 위해서다.
 */
export default function ConnectorDetailSkeleton() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-label="연동 정보 불러오는 중">
      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-5 w-28" />
        <div className="border-line-normal-assistive bg-fill-normal-strong overflow-hidden rounded-xl border">
          <div className="border-line-normal-neutral flex items-center justify-between border-b px-4 py-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>
          <div className="flex items-center justify-between px-4 py-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-5 w-32" />
        <div className="border-line-normal-assistive bg-fill-normal-strong flex items-center justify-center rounded-xl border px-4 py-3">
          <Skeleton className="h-4 w-48" />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-5 w-36" />
        <div className="border-line-normal-assistive bg-fill-normal-strong flex flex-col overflow-hidden rounded-xl border pt-2 pb-3">
          {Array.from({ length: RESOURCE_ROW_COUNT }, (_, i) => (
            <div key={i} className="flex h-13 items-center gap-3 px-4 py-3">
              <Skeleton className="size-8 shrink-0 rounded-full" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-3 w-24 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
