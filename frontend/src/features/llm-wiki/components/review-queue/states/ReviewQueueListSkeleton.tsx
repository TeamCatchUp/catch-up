import { Skeleton } from '@/shared/components/ui/skeleton';

const SKELETON_ROW_COUNT = 6;

/** 검토 큐 좌측 목록의 첫 로딩 골격. 행 여백·구분선은 데이터 행과 같은 값이다. */
export default function ReviewQueueListSkeleton() {
  return (
    <div role="status" aria-label="변경사항 목록 불러오는 중">
      {Array.from({ length: SKELETON_ROW_COUNT }, (_, index) => (
        <div key={index} className="border-line-normal-neutral flex w-full flex-col gap-3 border-b px-4 py-3">
          <Skeleton className="h-5.5 w-full max-w-52" />
          <Skeleton className="h-5 w-20" />
        </div>
      ))}
    </div>
  );
}
