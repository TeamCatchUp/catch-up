'use client';

import { useState } from 'react';

import { useAdminIntegrationViewModel } from '../../hooks/useAdminIntegrationViewModel';
import type { IntegrationService } from '../../types/integrationModel';
import IntegrationManagementSection from '../management/IntegrationManagementSection';

/**
 * 관리자 — 커넥터 연결 페이지.
 * 내용물은 구 레이아웃 그대로다. 신규 화면 이식은 계획 ②·③에서 한다.
 */
export default function ConnectorsPageClient() {
  const [selectedService, setSelectedService] = useState<IntegrationService>('jira');
  const { integrationMenu, getConnectorDetail } = useAdminIntegrationViewModel();

  return (
    <section className="mx-auto flex w-full flex-col gap-6 px-16 pt-9 pb-30 min-[1440px]:max-w-287">
      <h1 className="text-heading-xlarge text-text-normal-normal">협업툴 연동</h1>

      <section className="flex flex-col gap-2.5">
        <h2 className="text-heading-large text-text-normal-normal">협업툴 연동 관리</h2>
        <IntegrationManagementSection
          integrationMenu={integrationMenu}
          selectedService={selectedService}
          onSelectService={setSelectedService}
          detail={getConnectorDetail(selectedService)}
        />
      </section>
    </section>
  );
}
