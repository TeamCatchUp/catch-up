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

/** 미연동 상태 — '완료' 제외 narrow type. UnusedTag/AccountEdit 셀의 status prop과 호환. */
export type UnlinkedStatus = '미사용' | '미등록';

/**
 * 셀 모드 + 모드별 narrow된 status를 함께 묶은 discriminated union.
 * UsersTableRow의 switch가 이걸 받으면 cast(`as '미사용' | '미등록'`) 없이 type-safe하게 분기.
 */
export type CellModeResult =
  | { mode: 'linked' }
  | { mode: 'unused-tag'; status: UnlinkedStatus }
  | { mode: 'account-edit'; status: UnlinkedStatus };

export type CellMode = CellModeResult['mode'];

interface SelectCellModeArgs {
  status: MemberIntegrationStatus;
  isEditMode: boolean;
}

/**
 * 셀 모드 결정 — 단일 진실의 원천.
 *
 * | status        | isEditMode | mode         |
 * |---------------|------------|--------------|
 * | 완료          | any        | linked       |
 * | 미사용/미등록 | false      | unused-tag   |
 * | 미사용/미등록 | true       | account-edit |
 */
export const selectCellMode = ({ status, isEditMode }: SelectCellModeArgs): CellModeResult => {
  if (status === '완료') return { mode: 'linked' };
  // 여기서 status는 '완료' 제외 → UnlinkedStatus로 자동 narrow됨.
  if (!isEditMode) return { mode: 'unused-tag', status };
  return { mode: 'account-edit', status };
};

/**
 * 행의 dot 색상 결정 — 노출 중인 services 컬럼이 모두 '완료'면 초록(positive), 아니면 빨강.
 * 채널톡 단독 모드(services=['channel_talk'])에선 채널톡만 평가됨.
 */
export const isRowFullyLinked = (
  statusByService: Record<IntegrationService, MemberIntegrationStatus>,
  services: IntegrationService[],
): boolean => services.every((s) => statusByService[s] === '완료');
