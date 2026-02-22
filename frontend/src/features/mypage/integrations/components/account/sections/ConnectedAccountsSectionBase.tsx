import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { USE_MOCK } from '@/shared/mocks/config';
import { MOCK_ACCOUNT_INFO_MAP, MOCK_SELECTABLE_ROWS } from '@/shared/mocks/integration';
import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import { INTEGRATION_ACCOUNTS } from '../../../constants/integrations';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
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

const buildModalRow = (accountInfo: IntegrationAccountInfo, service: IntegrationService): MemberIntegrationRow => ({
  userKey: `${accountInfo.userEmail}:${accountInfo.userId}`,
  userName: accountInfo.userName || '-',
  email: accountInfo.userEmail || '-',
  phone: '-',
  department: '-',
  teamSizeLabel: '-',
  picture: null,
  accountIdByService: {
    [service]: accountInfo.userId || '-',
  },
  statusByService: {
    jira: service === 'jira' ? '완료' : '미사용',
    github: service === 'github' ? '완료' : '미사용',
    slack: service === 'slack' ? '완료' : '미사용',
    confluence: service === 'confluence' ? '완료' : '미사용',
  },
});

/** sync-status mappings → 서비스별 accountId 포함 행 변환 */
const getAccountId = (
  mapping: { githubLogin: string | null; atlassianEmail: string | null; slackEmail: string | null },
  service: IntegrationService,
): string | undefined => {
  switch (service) {
    case 'github':
      return mapping.githubLogin ?? undefined;
    case 'jira':
    case 'confluence':
      return mapping.atlassianEmail ?? undefined;
    case 'slack':
      return mapping.slackEmail ?? undefined;
  }
};

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
  const [selectedService, setSelectedService] = useState<IntegrationService>('jira');

  const resolvedCards = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((account) => {
        const accountInfo =
          accountInfoMap?.[account.service] ?? (USE_MOCK ? MOCK_ACCOUNT_INFO_MAP[account.service] : EMPTY_ACCOUNT_INFO);

        return {
          account,
          accountInfo,
          modalRow: buildModalRow(accountInfo, account.service),
        };
      }),
    [accountInfoMap],
  );

  const { data: syncStatus } = useQuery({
    ...adminConnectorQueries.userSyncStatus(),
    enabled: !USE_MOCK,
  });

  const allRows = useMemo<MemberIntegrationRow[]>(() => {
    if (USE_MOCK) return MOCK_SELECTABLE_ROWS;
    if (!syncStatus?.mappings) return [];

    return syncStatus.mappings.map((mapping) => {
      const accountIdByService: Partial<Record<IntegrationService, string>> = {};
      const statusByService = {} as Record<IntegrationService, '미사용' | '완료' | '미등록'>;

      for (const svc of ['jira', 'github', 'slack', 'confluence'] as IntegrationService[]) {
        const id = getAccountId(mapping, svc);
        if (id) accountIdByService[svc] = id;
        statusByService[svc] = id ? '완료' : '미등록';
      }

      return {
        userKey: mapping.name,
        userName: mapping.name,
        email: mapping.atlassianEmail ?? mapping.slackEmail ?? '-',
        phone: '-',
        department: '-',
        teamSizeLabel: '-',
        picture: null,
        accountIdByService,
        statusByService,
      };
    });
  }, [syncStatus]);

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
              setSelectedService(account.service);
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
          service={selectedService}
          serviceName={serviceName}
        />
      )}

      {activeModal === 'register' && (
        <AccountRegisterModal
          open
          onOpenChange={handleModalClose}
          allRows={allRows}
          service={selectedService}
          serviceName={serviceName}
        />
      )}
    </section>
  );
};

export default ConnectedAccountsSectionBase;
