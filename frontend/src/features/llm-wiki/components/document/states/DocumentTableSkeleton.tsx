import { Skeleton } from '@/shared/components/ui/skeleton';

import { DASHBOARD_DOCUMENT_TABLE_SHELL } from '../DashboardDocumentRow';
import { FOLDER_DOCUMENT_META_GRID, type FolderDocumentRowKind } from '../FolderDocumentRow';

const DEFAULT_ROW_COUNT = 5;

interface DocumentTableSkeletonProps {
  /** 그릴 골격 행 수. 쪽 크기와 무관한 표시상의 값이다 */
  rowCount?: number;
  /** 제목 아래 경로 줄이 있는 행인지 — 대시보드 표만 그 줄을 갖는다 */
  withPath?: boolean;
  /** 목적지 표의 메타 열 구성 — folder는 최근 활동 한 칸뿐이다 */
  kind?: FolderDocumentRowKind;
  /** 최근 활동 열 정렬 — 우측 정렬인 대시보드 표만 end를 준다 */
  activityAlign?: 'center' | 'end';
}

/**
 * 문서·폴더 표의 첫 로딩 골격. 데이터 행과 같은 셸·열 상수를 써서 로드 후 열이 움직이지 않는다.
 * 텍스트를 넣지 않는다 — 승인되지 않은 카피를 만들지 않기 위해서다.
 */
export default function DocumentTableSkeleton({
  rowCount = DEFAULT_ROW_COUNT,
  withPath = false,
  kind = 'document',
  activityAlign = 'center',
}: DocumentTableSkeletonProps) {
  return (
    <div role="status" aria-label="목록 불러오는 중" className="flex flex-col gap-1">
      {Array.from({ length: rowCount }, (_, index) => (
        <div key={index} className={DASHBOARD_DOCUMENT_TABLE_SHELL}>
          {/* 이름 열 — 데이터 행과 같이 이 슬롯만 폭을 흡수한다 */}
          <span className="flex min-w-55 flex-1 items-center gap-4">
            <Skeleton className="size-10 shrink-0 rounded-lg" />
            <span className="flex min-w-0 flex-1 flex-col justify-center gap-0.5">
              <Skeleton className="h-5.5 w-full max-w-72" />
              {withPath && <Skeleton className="h-7 w-45 rounded-full" />}
            </span>
          </span>

          <span className={FOLDER_DOCUMENT_META_GRID[kind]}>
            {kind === 'document' && (
              <>
                <span className="flex min-w-0 items-center gap-3">
                  <Skeleton className="size-6.25 shrink-0 rounded-xl" />
                  <Skeleton className="h-5.5 w-16" />
                </span>
                <Skeleton className="h-7.5 w-22 rounded-lg" />
              </>
            )}
            <Skeleton
              className={activityAlign === 'end' ? 'h-5.5 w-14 justify-self-end' : 'h-5.5 w-14 justify-self-center'}
            />
          </span>
        </div>
      ))}
    </div>
  );
}
