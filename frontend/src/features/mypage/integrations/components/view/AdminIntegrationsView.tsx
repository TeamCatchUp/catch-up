import { useState } from 'react';

import { cn } from '@/shared/utils/cn';

import { useAdminIntegrationViewModel } from '../../hooks/useAdminIntegrationViewModel';
import type { AdminIntegrationTab, IntegrationService } from '../../types/integrations.types';
import ConnectedAccountsAdminSection from '../account/ConnectedAccountsAdminSection';
import IntegrationManagementSection from '../management/IntegrationManagementSection';

/** 관리자 협업툴 연동 화면 */
const AdminIntegrationsView = () => {
  const [activeTab, setActiveTab] = useState<AdminIntegrationTab>('my');
  const [selectedService, setSelectedService] = useState<IntegrationService>('jira');
  const { integrationMenu, lastSyncedAt, spaceRows } = useAdminIntegrationViewModel();

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-30">
      <h1 className="text-heading-xlarge text-gray-80">협업툴 연동</h1>

      <div className="flex flex-col gap-10">
        <div className="flex flex-col gap-8">
          <div className="flex items-center gap-6">
            <button
              type="button"
              onClick={() => setActiveTab('my')}
              className={cn(
                'text-heading-large cursor-pointer border-b-2 pb-1 transition-colors',
                activeTab === 'my' ? 'border-gray-80 text-gray-80' : 'border-transparent text-gray-40',
              )}
            >
              나의 연동 상태
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('member')}
              className={cn(
                'text-heading-large cursor-pointer border-b-2 pb-1 transition-colors',
                activeTab === 'member' ? 'border-gray-80 text-gray-80' : 'border-transparent text-gray-40',
              )}
            >
              이용자 연동
            </button>
          </div>

          <ConnectedAccountsAdminSection />
        </div>

        {activeTab === 'my' ? (
          <section className="flex flex-col gap-2.5">
            <h2 className="text-heading-small text-gray-80">협업툴 연동 관리</h2>
            <IntegrationManagementSection
              integrationMenu={integrationMenu}
              selectedService={selectedService}
              onSelectService={setSelectedService}
              lastSyncedAt={lastSyncedAt}
              spaceRows={spaceRows}
            />
          </section>
        ) : (
          <div className="border-neutral-3 bg-neutral-1 text-body-small text-gray-60 rounded-xl border px-5 py-4">
            이용자 연동 탭은 API/정책 확정 후 구현할 예정입니다.
          </div>
        )}
      </div>
    </section>
  );
};

export default AdminIntegrationsView;
