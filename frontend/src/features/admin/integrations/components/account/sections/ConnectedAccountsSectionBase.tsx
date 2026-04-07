import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import type { IntegrationService } from '@/shared/types/integrationService';
import { cn } from '@/shared/utils/cn';

import { INTEGRATION_ACCOUNTS } from '../../../constants/integrationsConfig';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type { PreMappingInfo, UserSyncItem } from '../../../types/integrationApi';
import type { IntegrationAccountInfo, MemberIntegrationRow } from '../../../types/integrationModel';
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
  serviceInfoByService: {
    [service]: { name: accountInfo.userName, identifier: accountInfo.userEmail, picture: null },
  },
  statusByService: {
    jira: service === 'jira' ? '완료' : '미사용',
    github: service === 'github' ? '완료' : '미사용',
    slack: service === 'slack' ? '완료' : '미사용',
    confluence: service === 'confluence' ? '완료' : '미사용',
  },
});

/** UserSyncItem에서 서비스별 PreMappingInfo 추출 */
const getServiceInfo = (item: UserSyncItem, service: IntegrationService): PreMappingInfo | null => {
  switch (service) {
    case 'jira':
    case 'confluence':
      return item.atlassian;
    case 'github':
      return item.github;
    case 'slack':
      return item.slack;
  }
};

type ModalType = 'edit' | 'register' | null;

/** 연동 계정 정보 섹션 공통 베이스 */
export default function ConnectedAccountsSectionBase({
  variant,
  sectionGapClassName,
  accountInfoMap,
}: ConnectedAccountsSectionBaseProps) {
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [selectedRow, setSelectedRow] = useState<MemberIntegrationRow | null>(null);
  const [serviceName, setServiceName] = useState('');
  const [selectedService, setSelectedService] = useState<IntegrationService>('jira');

  const resolvedCards = useMemo(
    () =>
      INTEGRATION_ACCOUNTS.map((account) => {
        const accountInfo = accountInfoMap?.[account.service] ?? EMPTY_ACCOUNT_INFO;

        return {
          account,
          accountInfo,
          modalRow: buildModalRow(accountInfo, account.service),
        };
      }),
    [accountInfoMap],
  );

  const { data: syncStatus } = useQuery({
    ...adminConnectorQueries.userSyncStatus({ filterType: 'all', page: 1, size: 100 }),
    enabled: variant === 'admin',
  });

  const allRows = useMemo<MemberIntegrationRow[]>(() => {
    if (!syncStatus?.items) return [];

    return syncStatus.items.map((item) => {
      const serviceInfoByService: Partial<Record<IntegrationService, PreMappingInfo>> = {};
      const statusByService = {} as Record<IntegrationService, '미사용' | '완료' | '미등록'>;

      for (const svc of ['jira', 'github', 'slack', 'confluence'] as IntegrationService[]) {
        const info = getServiceInfo(item, svc);
        if (info) serviceInfoByService[svc] = info;
        statusByService[svc] = info ? '완료' : '미등록';
      }

      return {
        userKey: item.name,
        userName: item.name,
        email: item.email,
        serviceInfoByService,
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
      <h2 className="text-heading-large text-content-normal">연결된 계정 정보</h2>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-5">
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
}
