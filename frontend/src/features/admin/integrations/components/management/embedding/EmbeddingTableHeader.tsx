import { cn } from '@/shared/utils/cn';

import { EMBEDDING_ROW_GRID } from './embeddingTableGrid';

/**
 * 임베딩 현황 탭의 표 헤더.
 * 진행중 섹션(`17125:114636`)과 히스토리(`17145:116622`)가 **같은 4열**을 쓴다.
 * 헤더 716×36, 열 x: 대상 12 / 상태 340 / 시각 506 / 액션 672.
 *
 * 열 폭은 {@link EMBEDDING_ROW_GRID}가 정한다. display를 grid로 덮으면
 * 표 시맨틱이 사라지므로 `role`을 직접 준다.
 */
export default function EmbeddingTableHeader() {
  return (
    <thead role="rowgroup" className="block">
      <tr role="row" className={cn(EMBEDDING_ROW_GRID, 'h-9')}>
        {/* truncate: 좁은 슬롯에서 라벨이 두 줄로 접혀 헤더가 36을 넘는 걸 막는다 */}
        <th
          role="columnheader"
          scope="col"
          className="text-body-xsmall text-text-normal-alternative truncate text-left font-medium"
        >
          임베딩 대상
        </th>
        <th
          role="columnheader"
          scope="col"
          className="text-body-xsmall text-text-normal-alternative truncate text-left font-medium"
        >
          임베딩 상태
        </th>
        <th
          role="columnheader"
          scope="col"
          className="text-body-xsmall text-text-normal-alternative truncate text-left font-medium"
        >
          실행 시각
        </th>
        <th role="columnheader" scope="col">
          <span className="sr-only">작업</span>
        </th>
      </tr>
    </thead>
  );
}
