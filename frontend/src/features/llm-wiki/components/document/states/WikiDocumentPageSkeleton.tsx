import { Skeleton } from '@/shared/components/ui/skeleton';
import { cn } from '@/shared/utils/cn';

/** 골격 문단의 줄 폭. 마지막 줄만 짧게 끝나 실제 문단처럼 보인다 */
const BLOCK_LINE_WIDTHS = ['w-full', 'w-full', 'w-3/5'] as const;
const BLOCK_COUNT = 3;

/**
 * 문서 열람의 첫 로딩 골격. 헤더 자리와 본문 폭을 실제 화면과 같은 값으로 잡아 로드 후 글이 움직이지 않는다.
 * 발행판이 없어 404가 난 경우는 로딩이 아니라 이 골격이 서지 않는다.
 */
export default function WikiDocumentPageSkeleton() {
  return (
    <section className="flex min-h-full flex-col">
      {/* breadcrumb 헤더 자리 — 경로 이름이 오기 전이라 셸만 남긴다 */}
      <div aria-hidden className="border-line-normal-neutral h-13 shrink-0 border-b" />

      <div
        role="status"
        aria-label="문서 불러오는 중"
        className="mx-auto flex w-full max-w-260 flex-1 flex-col gap-6 px-6 py-9"
      >
        <div className="flex flex-col gap-3">
          <Skeleton className="h-6.5 w-full max-w-120" />
          <Skeleton className="h-5.5 w-28" />
        </div>

        <div className="flex flex-col gap-8">
          {Array.from({ length: BLOCK_COUNT }, (_, blockIndex) => (
            <div key={blockIndex} className="flex flex-col gap-3">
              <Skeleton className="h-6.5 w-full max-w-60" />
              {BLOCK_LINE_WIDTHS.map((width, lineIndex) => (
                <Skeleton key={lineIndex} className={cn('h-5.5', width)} />
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
