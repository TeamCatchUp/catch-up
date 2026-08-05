import type { ConnectorDetailStatus } from '../../../types/integrationModel';
import ConnectorDetailSkeleton from './ConnectorDetailSkeleton';
import ConnectorErrorNotice from './ConnectorErrorNotice';

interface ConnectorStateBoundaryProps {
  status: ConnectorDetailStatus;
  /** INTEGRATION_ACCOUNTS의 name — 오류 문구에만 쓰인다 */
  serviceName: string;
  children: React.ReactNode;
}

/**
 * 커넥터 상세의 로딩·오류 경계.
 * 쿼리를 직접 구독하지 않는다 — 판정은 useAdminIntegrationViewModel이 독점한다.
 * 5개 도구가 모두 이 경계를 지나므로 채널톡만 방어되던 불일치가 사라진다.
 */
export default function ConnectorStateBoundary({ status, serviceName, children }: ConnectorStateBoundaryProps) {
  if (status === 'loading') return <ConnectorDetailSkeleton />;
  if (status === 'error') return <ConnectorErrorNotice serviceName={serviceName} />;
  return <>{children}</>;
}
