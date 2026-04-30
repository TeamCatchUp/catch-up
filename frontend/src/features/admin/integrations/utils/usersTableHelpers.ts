import type { IntegrationService, MemberIntegrationStatus } from '../types/integrationModel';

/**
 * UsersTable 데이터 흐름:
 *   API → useMemberIntegrationViewModel (status 결정)
 *       → buildMemberDisplayRows
 *       → UsersStatusSection (overrides 머지, services 결정)
 *       → UsersTable (이 helpers 사용)
 *           → selectCellMode → switch → cell component
 *
 * UsersTable은 filter·머지된 displayRows + 노출 services만 받음. 외부 상태 관리 안 함.
 */

export type CellMode = 'linked' | 'unused-tag' | 'account-edit';

interface SelectCellModeArgs {
  service: IntegrationService;
  status: MemberIntegrationStatus;
  isEditMode: boolean;
}

/**
 * 셀 모드 결정 — 단일 진실의 원천.
 *
 * | status        | service        | isEditMode | mode         |
 * |---------------|----------------|------------|--------------|
 * | 완료          | any            | any        | linked       |
 * | 미사용/미등록 | channel-talk   | any        | unused-tag*  |
 * | 미사용/미등록 | other          | false      | unused-tag   |
 * | 미사용/미등록 | other          | true       | account-edit |
 *
 * (*) 채널톡은 user-level 매핑 API 백엔드 미구현이라 isEditMode=true에서도 read-only로 강제.
 *     백엔드 합류 시 이 한 줄(`if (service === 'channel-talk')`)만 제거.
 */
export const selectCellMode = ({ service, status, isEditMode }: SelectCellModeArgs): CellMode => {
  if (status === '완료') return 'linked';
  if (service === 'channel-talk') return 'unused-tag';
  if (!isEditMode) return 'unused-tag';
  return 'account-edit';
};

/**
 * 행의 dot 색상 결정 — 노출 중인 services 컬럼이 모두 '완료'면 초록(positive), 아니면 빨강.
 * 채널톡 단독 모드(services=['channel-talk'])에선 채널톡만 평가됨.
 */
export const isRowFullyLinked = (
  statusByService: Record<IntegrationService, MemberIntegrationStatus>,
  services: IntegrationService[],
): boolean => services.every((s) => statusByService[s] === '완료');
