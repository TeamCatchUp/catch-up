/**
 * 임베딩 현황 탭의 표 헤더.
 * 진행중 섹션(`17125:114636`)과 히스토리(`17145:116622`)가 **같은 4열**을 쓴다.
 * 헤더 716×36, 열 x: 대상 12 / 상태 340 / 시각 506 / 액션 672.
 */
export default function EmbeddingTableHeader() {
  return (
    <thead>
      <tr className="h-9">
        <th scope="col" className="text-body-xsmall text-text-normal-alternative pr-4 pl-3 text-left font-medium">
          임베딩 대상
        </th>
        <th scope="col" className="text-body-xsmall text-text-normal-alternative w-37.5 pr-4 text-left font-medium">
          임베딩 상태
        </th>
        <th scope="col" className="text-body-xsmall text-text-normal-alternative w-37.5 pr-4 text-left font-medium">
          실행 시각
        </th>
        <th scope="col" className="w-11 pr-3">
          <span className="sr-only">작업</span>
        </th>
      </tr>
    </thead>
  );
}
