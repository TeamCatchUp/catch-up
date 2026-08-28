import { Skeleton } from '@/shared/components/ui/skeleton';

const DIFF_CARD_COUNT = 2;

/**
 * 검토 큐 상세의 첫 로딩 골격. 제목·요약 카드·변경 카드 순서와 간격을 데이터 화면과 맞춘다.
 * 바깥 패딩은 상세를 교체하는 모션 상자가 이미 갖고 있어 여기서 다시 두지 않는다.
 */
export default function ReviewQueueDetailSkeleton() {
  return (
    <div role="status" aria-label="변경사항 불러오는 중" className="flex flex-col gap-9">
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-full max-w-100" />
        <Skeleton className="h-5 w-24" />
      </div>

      <div className="border-line-normal-neutral flex flex-col gap-3 rounded-xl border px-5 py-4">
        <Skeleton className="h-5.5 w-40" />
        <Skeleton className="h-5.5 w-full" />
      </div>

      <div className="flex flex-col gap-3">
        <Skeleton className="h-6.5 w-28" />
        {Array.from({ length: DIFF_CARD_COUNT }, (_, index) => (
          <div key={index} className="border-line-normal-neutral flex flex-col gap-3 rounded-xl border p-5">
            <Skeleton className="h-5.5 w-32" />
            <Skeleton className="h-5.5 w-full" />
            <Skeleton className="h-5.5 w-2/3" />
          </div>
        ))}
      </div>
    </div>
  );
}
