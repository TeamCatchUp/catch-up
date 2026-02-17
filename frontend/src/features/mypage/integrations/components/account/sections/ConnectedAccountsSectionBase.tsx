import { useMemo, useState } from 'react';

import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_ACCOUNT_INFO_MAP, MOCK_SELECTABLE_ROWS } from '@/shared/mocks/integration';
import { cn } from '@/shared/utils/cn';

import { INTEGRATION_ACCOUNTS } from '../../../constants/integrations';
import type { IntegrationAccountInfo, MemberIntegrationRow } from '../../../types/integrations';
import ConnectedAccountCard from '../cards/ConnectedAccountCard';
import AccountEditModal from '../modals/AccountEditModal';
import AccountRegisterModal from '../modals/AccountRegisterModal';

interface ConnectedAccountsSectionBaseProps {
  variant: 'user' | 'admin';
  sectionGapClassName: string;
  accountInfoMap?: Partial<Record<string, IntegrationAccountInfo>>;
}

const EMPTY_ACCOUNT_INFO: IntegrationAccountInfo = {
  userName: '-',
  userId: '-',
  userEmail: '-',
};

const buildModalRow = (accountInfo: IntegrationAccountInfo): MemberIntegrationRow => ({
  userKey: `${accountInfo.userEmail}:${accountInfo.userId}`,
  userName: accountInfo.userName || '-',
  email: accountInfo.userEmail || '-',
  phone: '-',
  department: '-',
  teamSizeLabel: '-',
  picture: null,
  accountIdByService: {
    jira: accountInfo.userId || '-',
  },
  statusByService: {
    jira: '완료',
    github: '미사용',
    slack: '미사용',
    confluence: '미사용',
  },
});

type ModalType = 'edit' | 'register' | null;

/** 연동 계정 정보 섹션 공통 베이스 */
const ConnectedAccountsSectionBase = ({
  variant,
  sectionGapClassName,
  accountInfoMap,
}: ConnectedAccountsSectionBaseProps) => {
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [selectedRow, setSelectedRow] = useState<MemberIntegrationRow | null>(null);
  const [serviceName, setServiceName] = useState('');

  const resolvedCards = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((account) => {
        const accountInfo =
          accountInfoMap?.[account.service] ?? (USE_MOCK ? MOCK_ACCOUNT_INFO_MAP[account.service] : EMPTY_ACCOUNT_INFO);

        return {
          account,
          accountInfo,
          modalRow: buildModalRow(accountInfo),
        };
      }),
    [accountInfoMap],
  );

  const allRows = useMemo(
    () => (USE_MOCK ? MOCK_SELECTABLE_ROWS : resolvedCards.map((card) => card.modalRow)),
    [resolvedCards],
  );

  const handleModalClose = (open: boolean) => {
    if (!open) {
      setActiveModal(null);
      setSelectedRow(null);
    }
  };

  return (
    <section className={cn('flex flex-col', sectionGapClassName)}>
      <h2 className="text-heading-large text-gray-80">연결된 계정 정보</h2>
      <div className="flex flex-nowrap items-center gap-5 overflow-x-auto">
        {resolvedCards.map(({ account, accountInfo, modalRow }) => (
          <ConnectedAccountCard
            key={account.service}
            account={account}
            accountInfo={accountInfo}
            variant={variant}
            onEditClick={() => {
              const isConnected =
                accountInfo.userName !== '-' && accountInfo.userId !== '-' && accountInfo.userEmail !== '-';
              setActiveModal(isConnected ? 'edit' : 'register');
              setSelectedRow(modalRow);
              setServiceName(account.name);
            }}
          />
        ))}
      </div>

      {selectedRow && activeModal === 'edit' && (
        <AccountEditModal
          open
          onOpenChange={handleModalClose}
          selectedRow={selectedRow}
          allRows={allRows}
          serviceName={serviceName}
        />
      )}

      {activeModal === 'register' && (
        <AccountRegisterModal open onOpenChange={handleModalClose} allRows={allRows} serviceName={serviceName} />
      )}
    </section>
  );
};

export default ConnectedAccountsSectionBase;
