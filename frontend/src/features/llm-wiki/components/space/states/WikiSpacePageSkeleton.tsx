import { Skeleton } from '@/shared/components/ui/skeleton';

import { DashboardDocumentTableHeader } from '../../document/DashboardDocumentRow';
import DocumentTableSkeleton from '../../document/states/DocumentTableSkeleton';

/**
 * 채널·폴더 화면의 첫 로딩 골격. 이름을 아직 몰라 헤더·제목까지 골격이고,
 * 커버·패딩·표 열은 실제 화면과 같은 값이라 로드 후 표가 제자리에 선다.
 */
export default function WikiSpacePageSkeleton() {
  return (
    <div className="flex flex-col">
      {/* breadcrumb 헤더 자리 — 경로 이름이 오기 전이라 셸만 남긴다 */}
      <div aria-hidden className="border-line-normal-neutral h-13 shrink-0 border-b" />
      <div aria-hidden className="bg-fill-normal-strong h-50 shrink-0" />

      <div role="status" aria-label="불러오는 중" className="flex flex-col gap-9 px-20 py-9">
        <div className="flex items-center gap-5">
          <Skeleton className="size-10 shrink-0 rounded-lg" />
          <Skeleton className="h-8 w-full max-w-80" />
        </div>

        <div className="flex flex-col">
          <DashboardDocumentTableHeader />
          <DocumentTableSkeleton />
        </div>
      </div>
    </div>
  );
}
