import type { UserMappingRow } from '../types/userMappingModel';

/**
 * "미사용" 저장이 반영되지 않은 Atlassian 셀 탐지.
 *
 * 백엔드의 atlassian 편집은 Jira 매핑만 지우는데, 목록 응답의 atlassian 필드는
 * Jira가 없으면 Confluence 매핑으로 채워진다. 그래서 Confluence로 매핑된 이용자는
 * "미사용" 저장 뒤에도 재조회 시 계정이 되살아난다 — 이 경우를 저장 직후 재조회
 * 데이터에서 감지해 사용자에게 알린다(계약 공백 T-2가 닫히기 전까지의 완화).
 */
export const findUnappliedAtlassianUnused = (
  rows: readonly UserMappingRow[],
  savedUserKeys: readonly string[],
): UserMappingRow[] =>
  rows.filter(
    (row) =>
      savedUserKeys.includes(row.id) && row.accounts.atlassian != null && row.accounts.atlassian !== 'unused',
  );
