import { useCallback, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { cn } from '@/shared/utils/cn';

import { useAdminIntegrationViewModel } from '../../hooks/useAdminIntegrationViewModel';
import type { AdminIntegrationTab, IntegrationService } from '../../types/integrations';
import ConnectedAccountsAdminSection from '../account/sections/ConnectedAccountsAdminSection';
import IntegrationManagementSection from '../management/IntegrationManagementSection';
import IntegrationsSection from '../member/sections/IntegrationsSection';

const DEFAULT_TAB: AdminIntegrationTab = 'my';
const isValidTab = (v: string | null): v is AdminIntegrationTab => v === 'my' || v === 'member';

/** 관리자 협업툴 연동 화면 */
const AdminIntegrationsView = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab');
  const activeTab: AdminIntegrationTab = isValidTab(tabParam) ? tabParam : DEFAULT_TAB;

  const setActiveTab = useCallback(
    (tab: AdminIntegrationTab) => {
      router.replace(`/mypage/integrations?tab=${tab}`);
    },
    [router],
  );

  const [selectedService, setSelectedService] = useState<IntegrationService>('jira');
  const { integrationMenu, getConnectorDetail } = useAdminIntegrationViewModel();

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-30">
      <h1 className="text-heading-xlarge text-content-normal">협업툴 연동</h1>

      <div className="flex flex-col gap-8">
        <div className="flex items-center gap-6">
          <button
            type="button"
            onClick={() => setActiveTab('my')}
            className={cn(
              'text-heading-large cursor-pointer border-b-2 pb-1 transition-colors',
              activeTab === 'my' ? 'border-content-normal text-content-normal' : 'text-content-assistive border-transparent',
            )}
          >
            내 연동
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('member')}
            className={cn(
              'text-heading-large cursor-pointer border-b-2 pb-1 transition-colors',
              activeTab === 'member' ? 'border-content-normal text-content-normal' : 'text-content-assistive border-transparent',
            )}
          >
            이용자 연동
          </button>
        </div>

        {activeTab === 'my' ? (
          <section className="flex flex-col gap-10">
            <ConnectedAccountsAdminSection />
            <section className="flex flex-col gap-2.5">
              <h2 className="text-heading-large text-content-normal">협업툴 연동 관리</h2>
              <IntegrationManagementSection
                integrationMenu={integrationMenu}
                selectedService={selectedService}
                onSelectService={setSelectedService}
                detail={getConnectorDetail(selectedService)}
              />
            </section>
          </section>
        ) : (
          <IntegrationsSection />
        )}
      </div>
    </section>
  );
};

export default AdminIntegrationsView;
