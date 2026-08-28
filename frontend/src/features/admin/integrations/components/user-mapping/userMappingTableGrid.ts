/**
 * 이용자 매핑 표의 행 grid 템플릿 — `embeddingTableGrid.ts`와 같은 패턴.
 * 커넥터 열 수가 필터에 따라 4↔1로 바뀌므로 템플릿 상수를 통째로 교체한다.
 * 높이는 고정하지 않는다. 실측 근거: docs/specs/2026-08-04-cam256-figma-measurements-design.md
 */
export const MAPPING_ROW_GRID_FULL =
  'grid grid-cols-[8px_minmax(0,140px)_repeat(4,minmax(0,1fr))] items-center gap-4 px-6';

export const MAPPING_ROW_GRID_SINGLE = 'grid grid-cols-[8px_minmax(0,1fr)_minmax(0,1fr)] items-center gap-4 px-6';
