/**
 * 임베딩 표(진행중·히스토리 공용)의 행 grid 템플릿.
 *
 * `<table>` 열 알고리즘으로는 위아래로 쌓인 두 표의 열을 맞출 수 없어, 행만 grid로
 * 깔고 `role`로 표 시맨틱을 되살린다. 높이는 고정하지 않는다(`py-2` + 사용처 `min-h-*`) —
 * 내용이 커지면 행이 자라야 한다. 고정 폭의 실측 근거:
 * docs/specs/2026-08-04-cam256-figma-measurements-design.md
 */
export const EMBEDDING_ROW_GRID = 'grid grid-cols-[minmax(0,1fr)_150px_150px_32px] items-center gap-4 px-3 py-2';

/** 임베딩 대상 목록의 행 grid 템플릿 — 범위 열을 고정해 헤더·본문 열이 어긋나지 않게 한다 */
export const RESOURCE_ROW_GRID = 'grid grid-cols-[minmax(0,1fr)_180px] items-center gap-4 px-3 py-2';
