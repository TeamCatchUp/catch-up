import type { ConnectorDetailStatus } from '../types/integrationModel';

/** 쿼리 상태 판정에 필요한 최소 플래그 — TanStack Query 결과에서 추려 넘긴다 */
export interface ConnectorQueryFlags {
  isLoading: boolean;
  isError: boolean;
}

/**
 * connection-status와 target-status 두 쿼리를 합쳐 화면 상태를 판정한다.
 * 우선순위는 error > loading > ready — 하나라도 실패하면 화면은 연동 여부를 모르는 상태이므로
 * "연동 안됨"이나 "연동된 항목이 없습니다."를 보여주면 거짓이 된다.
 */
export const resolveConnectorStatus = (
  connection: ConnectorQueryFlags,
  target: ConnectorQueryFlags,
): ConnectorDetailStatus => {
  if (connection.isError || target.isError) return 'error';
  if (connection.isLoading || target.isLoading) return 'loading';
  return 'ready';
};
