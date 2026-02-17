import type { IntegrationService, MemberIntegrationRow, MemberIntegrationStatus } from './integrations';

/** 이용자 연동 테이블 렌더 전용 행 모델 */
export interface MemberDisplayRow {
  renderKey: string;
  row: MemberIntegrationRow;
  displayStatusByService: Record<IntegrationService, MemberIntegrationStatus>;
}
