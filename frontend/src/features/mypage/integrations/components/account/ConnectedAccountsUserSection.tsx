import { MOCK_INTEGRATION_ACCOUNT_INFO } from '@/shared/mocks/integration/data';

import { INTEGRATION_ACCOUNTS } from '../../constants/integrations.constants';
import ConnectedAccountCard from './ConnectedAccountCard';

/** 일반 사용자용 연동 계정 정보 섹션 */
const ConnectedAccountsUserSection = () => {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-heading-large text-gray-80">연결된 계정 정보</h2>
      <div className="flex flex-nowrap items-center gap-5 overflow-x-auto">
        {INTEGRATION_ACCOUNTS.map((account) => (
          <ConnectedAccountCard
            key={account.service}
            account={account}
            accountInfo={MOCK_INTEGRATION_ACCOUNT_INFO}
            variant="user"
          />
        ))}
      </div>
    </section>
  );
};

export default ConnectedAccountsUserSection;
