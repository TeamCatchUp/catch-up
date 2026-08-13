import { Skeleton } from '@/shared/components/ui/skeleton';
import { cn } from '@/shared/utils/cn';

import { ONBOARDING_CHANNEL_TABLE_GRID } from '../onboardingChannelTableGrid';

const SKELETON_ROW_COUNT = 5;

/**
 * 채널 목록 초기 로딩 골격. 데이터 표와 같은 열 상수를 써서 로드 후 레이아웃이 움직이지 않는다.
 * 텍스트를 넣지 않는다 — 승인되지 않은 카피를 만들지 않기 위해서다.
 */
export default function OnboardingChannelTableSkeleton() {
  return (
    <div
      role="status"
      aria-label="채널 목록 불러오는 중"
      className="border-line-normal-neutral overflow-hidden rounded-xl border"
    >
      <div className={cn(ONBOARDING_CHANNEL_TABLE_GRID, 'border-line-normal-neutral border-b py-3')}>
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-5 w-20 justify-self-end" />
      </div>
      {Array.from({ length: SKELETON_ROW_COUNT }, (_, index) => (
        <div key={index} className={cn(ONBOARDING_CHANNEL_TABLE_GRID, 'py-3')}>
          <div className="flex min-w-0 items-center gap-3">
            <Skeleton className="size-5 shrink-0 rounded-full" />
            <Skeleton className="h-5 w-full max-w-80" />
          </div>
          <Skeleton className="h-5 w-24 justify-self-end" />
        </div>
      ))}
    </div>
  );
}
