import type { MemberIntegrationRow } from '../types/integrations';
import type { MemberDisplayRow } from '../types/memberDisplay';

/** 이용자 연동 테이블 행을 UI 렌더용 모델로 변환 */
export const buildMemberDisplayRows = (rows: MemberIntegrationRow[]): MemberDisplayRow[] => {
  if (rows.length === 0) return [];

  return rows.map((row) => ({
    renderKey: row.userKey,
    row,
    displayStatusByService: row.statusByService,
  }));
};
