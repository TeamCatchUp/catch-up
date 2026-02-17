import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_INTEGRATION_ACCOUNT_INFO } from '@/shared/mocks/integration';
import { cn } from '@/shared/utils/cn';

import { INTEGRATION_ACCOUNTS } from '../../constants/integrations';
import type { IntegrationAccountInfo } from '../../types/integrations';
import ConnectedAccountCard from './ConnectedAccountCard';

interface ConnectedAccountsSectionBaseProps {
  variant: 'user' | 'admin';
  sectionGapClassName: string;
  /** 실제 API 모드에서 서비스별 계정 정보를 전달 (미전달 시 mock fallback) */
  accountInfoMap?: Partial<Record<string, IntegrationAccountInfo>>;
}

const EMPTY_ACCOUNT_INFO: IntegrationAccountInfo = {
  userName: '-',
  userId: '-',
  userEmail: '-',
};

/** 연동 계정 정보 섹션 공통 베이스 */
const ConnectedAccountsSectionBase = ({
  variant,
  sectionGapClassName,
  accountInfoMap,
}: ConnectedAccountsSectionBaseProps) => {
  return (
    <section className={cn('flex flex-col', sectionGapClassName)}>
      <h2 className="text-heading-large text-gray-80">연결된 계정 정보</h2>
      <div className="flex flex-nowrap items-center gap-5 overflow-x-auto">
        {INTEGRATION_ACCOUNTS.map((account) => {
          const accountInfo =
            accountInfoMap?.[account.service] ?? (USE_MOCK ? MOCK_INTEGRATION_ACCOUNT_INFO : EMPTY_ACCOUNT_INFO);

          return (
            <ConnectedAccountCard key={account.service} account={account} accountInfo={accountInfo} variant={variant} />
          );
        })}
      </div>
    </section>
  );
};

export default ConnectedAccountsSectionBase;
