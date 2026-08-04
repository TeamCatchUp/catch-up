/**
 * 이용자 매핑 표의 열 정의 — `embeddingTableGrid.ts`와 같은 패턴.
 *
 * Figma 행 `17060:75372`(전체) · `17386:94452`(커넥터 필터):
 * `1040 = 24 | 점 8 | 16 | 사용자 | 16 | 커넥터 셀들 | 24`, 행 py 12, 내용 42(2줄 셀).
 *
 * 전체 뷰는 사용자 140 + 커넥터 4열(셀 max 165, 열 간 시각 여백은 셀 상한이 만든다).
 * 커넥터 필터 뷰는 사용자 476 + 커넥터 476 — 균등 1fr 2개.
 * 열 수가 상태에 따라 4↔1로 바뀌므로 템플릿 상수를 통째로 교체한다.
 *
 * 높이는 박지 않는다 — 행 66은 `py 12 + 2줄 셀 42`의 결과다(임베딩 표와 같은 원칙).
 */
export const MAPPING_ROW_GRID_FULL =
  'grid grid-cols-[8px_minmax(0,140px)_repeat(4,minmax(0,1fr))] items-center gap-4 px-6';

export const MAPPING_ROW_GRID_SINGLE = 'grid grid-cols-[8px_minmax(0,1fr)_minmax(0,1fr)] items-center gap-4 px-6';
