import { useState } from 'react';

import UnderlineTabs, { type UnderlineTabItem } from '@/shared/components/ui/underline-tabs';
import { useTabRouting } from '@/shared/hooks/useTabRouting';

import { useAdminIntegrationViewModel } from '../../hooks/useAdminIntegrationViewModel';
import type { AdminIntegrationTab, IntegrationService } from '../../types/integrationModel';
import IntegrationManagementSection from '../management/IntegrationManagementSection';
import IntegrationsSection from '../member/sections/IntegrationsSection';

const DEFAULT_TAB: AdminIntegrationTab = 'my';
const isValidTab = (v: string | null): v is AdminIntegrationTab => v === 'my' || v === 'member';

const TAB_ITEMS: UnderlineTabItem<AdminIntegrationTab>[] = [
  { value: 'my', label: '내 연동' },
  { value: 'member', label: '이용자 연동' },
];

/** 관리자 협업툴 연동 화면 */
export default function AdminIntegrationsView() {
  const [activeTab, setActiveTab] = useTabRouting<AdminIntegrationTab>((raw) => (isValidTab(raw) ? raw : DEFAULT_TAB));

  const [selectedService, setSelectedService] = useState<IntegrationService>('jira');
  const { integrationMenu, getConnectorDetail } = useAdminIntegrationViewModel();

  return (
    <section className="mx-auto flex w-full flex-col gap-6 px-16 pt-9 pb-30 min-[1440px]:max-w-287">
      <h1 className="text-heading-xlarge text-text-normal-normal">협업툴 연동</h1>

      <div className="flex flex-col gap-8">
        <UnderlineTabs
          items={TAB_ITEMS}
          value={activeTab}
          onValueChange={setActiveTab}
          ariaLabel="협업툴 연동 탭"
          panelIdPrefix="admin-integrations"
        />

        {activeTab === 'my' ? (
          <section className="flex flex-col gap-2.5">
            <h2 className="text-heading-large text-text-normal-normal">협업툴 연동 관리</h2>
            <IntegrationManagementSection
              integrationMenu={integrationMenu}
              selectedService={selectedService}
              onSelectService={setSelectedService}
              detail={getConnectorDetail(selectedService)}
            />
          </section>
        ) : (
          <IntegrationsSection />
        )}
      </div>
    </section>
  );
}
