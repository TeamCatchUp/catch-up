/**
 * 임베딩 현황 탭의 표 헤더.
 * 진행중 섹션(`17125:114636`)과 히스토리(`17145:116622`)가 **같은 4열**을 쓴다.
 * Figma 기준 열 x: 대상 12 / 상태 340 / 시각 506 / 액션 672 (표 716).
 *
 * 폭은 `table-auto`에 맡긴다. 상태·시각·액션은 `whitespace-nowrap`이라 내용만큼만
 * 차지하고, 대상 열이 `w-full`로 나머지를 먹은 뒤 `max-w-0`으로 truncate된다.
 * Figma의 150/150/44는 그 결과와 거의 같아서 고정할 이유가 없다 —
 * 고정하면 좁은 폭에서 대상 열이 먼저 무너져 가로 스크롤이 필요해진다.
 */
export default function EmbeddingTableHeader() {
  return (
    <thead>
      <tr className="h-9">
        {/* truncate: 좁은 슬롯에서 라벨이 두 줄로 접혀 헤더가 36을 넘는 걸 막는다 */}
        <th
          scope="col"
          className="text-body-xsmall text-text-normal-alternative w-full truncate pr-4 pl-3 text-left font-medium"
        >
          임베딩 대상
        </th>
        <th
          scope="col"
          className="text-body-xsmall text-text-normal-alternative pr-4 text-left font-medium whitespace-nowrap"
        >
          임베딩 상태
        </th>
        <th
          scope="col"
          className="text-body-xsmall text-text-normal-alternative pr-4 text-left font-medium whitespace-nowrap"
        >
          실행 시각
        </th>
        <th scope="col" className="pr-3">
          <span className="sr-only">작업</span>
        </th>
      </tr>
    </thead>
  );
}
