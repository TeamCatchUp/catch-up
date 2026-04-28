import { useState } from 'react';

import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconGithubLogo from '@/public/icons/logo/GitHub.svg';
import { API } from '@/shared/api/endpoints';
import Pagination from '@/shared/components/ui/pagination';
import { cn } from '@/shared/utils/cn';

import { RESOURCES_PER_PAGE } from '../../constants/integrationsConfig';
import { useChannelTalkViewModel } from '../../hooks/useChannelTalkViewModel';
import type { ConnectorDetail, IntegrationMenuItem, IntegrationService } from '../../types/integrationModel';
import ChannelTalkManagementPanel from './channelTalk/ChannelTalkManagementPanel';
import ConfluenceGuideSection from './ConfluenceGuideSection';
import GithubGuideSection from './GithubGuideSection';
import JiraGuideSection from './JiraGuideSection';
import SlackGuideSection from './SlackGuideSection';

/** 서비스별 리소스 아이템 아이콘 */
const RESOURCE_ICONS: Record<IntegrationService, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  jira: IconSpace,
  github: IconGithubLogo,
  slack: IconTag,
  confluence: IconSpace,
  'channel-talk': IconTag,
};

/** 서비스별 연동 설치 핸들러 */
const handleInstall = (service: IntegrationService) => {
  switch (service) {
    case 'slack':
      window.location.href = API.slack.install;
      break;
    case 'jira':
    case 'confluence':
      window.location.href = API.atlassian.install;
      break;
  }
};

interface IntegrationManagementSectionProps {
  integrationMenu: IntegrationMenuItem[];
  selectedService: IntegrationService;
  onSelectService: (service: IntegrationService) => void;
  detail: ConnectorDetail;
}

/** 관리자 협업툴 연동 관리 섹션 */
export default function IntegrationManagementSection({
  integrationMenu,
  selectedService,
  onSelectService,
  detail,
}: IntegrationManagementSectionProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const channelTalkState = useChannelTalkViewModel();

  // 서비스 변경 시 페이지 리셋 — 렌더 중 조정 (useEffect 이중 렌더 방지)
  const [prevService, setPrevService] = useState(selectedService);
  if (prevService !== selectedService) {
    setPrevService(selectedService);
    setCurrentPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(detail.resources.length / RESOURCES_PER_PAGE));
  const paginatedResources = detail.resources.slice(
    (currentPage - 1) * RESOURCES_PER_PAGE,
    currentPage * RESOURCES_PER_PAGE,
  );

  return (
    <div className="flex gap-8">
      <div className="flex flex-1 flex-col gap-4">
        {integrationMenu.map(({ service, Icon, actionText, connected }) => {
          const isSelected = selectedService === service;

          return (
            <button
              key={service}
              type="button"
              onClick={() => onSelectService(service)}
              className={cn(
                'shadow-card flex h-16 w-full cursor-pointer items-center justify-between rounded-xl border p-4',
                isSelected ? 'border-edge-primary bg-fill-normal' : 'border-edge-neutral bg-fill-normal',
              )}
            >
              <div className="flex min-w-0 items-center gap-3">
                <Icon className={service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0'} />
                <span className="text-heading-small text-content-normal truncate">{actionText}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                {connected ? (
                  <>
                    <IconCloudCheckFilled className="text-icon-primary h-5 w-5" />
                    <span className="text-body-xsmall text-icon-primary">연동됨</span>
                  </>
                ) : (
                  <>
                    <IconCloudOff className="text-content-assistive h-5 w-5" />
                    <span className="text-body-xsmall text-content-alternative">연동 안됨</span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex flex-2 flex-col gap-6">
        {selectedService === 'channel-talk' ? (
          <ChannelTalkManagementPanel state={channelTalkState} />
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <h3 className="text-heading-small text-content-normal">연동 상태 관리</h3>
              <div className="border-edge-neutral bg-fill-strong overflow-hidden rounded-xl border">
                <div className="border-edge-neutral flex h-13 items-center justify-between border-b px-4 py-3">
                  <span className="text-body-small text-content-neutral">연동 상태</span>
                  <div className="flex items-center gap-1">
                    {detail.connected ? (
                      <span className="text-body-xsmall text-icon-primary">연동됨</span>
                    ) : (
                      <>
                        <div className="flex items-center gap-1 px-1.5 py-1">
                          <IconCloudOff className="text-content-assistive size-5" />
                          <span className="text-body-xsmall text-content-alternative">연동 안됨</span>
                        </div>
                        {selectedService !== 'github' && (
                          <button
                            type="button"
                            onClick={() => handleInstall(selectedService)}
                            className="text-body-xsmall text-icon-primary cursor-pointer rounded-full px-1.5 py-1"
                          >
                            연동하기
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
                <div className="border-edge-neutral flex h-13 items-center justify-between border-b px-4 py-3">
                  <span className="text-body-small text-content-neutral">보안 관련 설명</span>
                  <button
                    type="button"
                    className="text-body-xsmall text-content-neutral flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1"
                  >
                    원문 보기
                    <IconOpenInNew className="h-4.5 w-4.5" />
                  </button>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <h3 className="text-heading-small text-content-neutral">연동된 데이터 범위</h3>
              <div className="border-edge-neutral bg-fill-strong text-body-small text-content-neutral flex h-10.75 items-center justify-center rounded-xl border px-5">
                {detail.dataRange}
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <h3 className="text-heading-small text-content-neutral">{detail.resourceLabel}</h3>
              <div className="border-edge-neutral bg-fill-strong flex flex-col items-center gap-3 overflow-hidden rounded-xl border pt-2 pb-3">
                {detail.resources.length > 0 ? (
                  <>
                    <div className="flex w-full flex-col">
                      {paginatedResources.map((row, index) => {
                        const ResourceIcon = RESOURCE_ICONS[selectedService];
                        return (
                          <div
                            key={`${row.name}-${index}`}
                            className="text-body-small text-content-neutral flex h-13 items-center gap-3 px-4 py-3"
                          >
                            <div className="border-edge-neutral bg-fill-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
                              <ResourceIcon className="size-5" />
                            </div>
                            <span className="flex-1 truncate">{row.name}</span>
                            {row.dateRange && row.dateRange !== '-' && (
                              <span className="text-label-xsmall text-content-neutral shrink-0 whitespace-nowrap">
                                {row.dateRange}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {totalPages > 1 && (
                      <>
                        <div className="w-full px-4">
                          <div className="border-edge-neutral border-t" />
                        </div>
                        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
                      </>
                    )}
                  </>
                ) : (
                  <div className="text-body-small text-content-assistive flex h-13 items-center px-4 py-3">
                    연동된 항목이 없습니다.
                  </div>
                )}
              </div>
            </div>

            {selectedService === 'jira' && <JiraGuideSection />}
            {selectedService === 'confluence' && <ConfluenceGuideSection />}
            {selectedService === 'github' && <GithubGuideSection />}
            {selectedService === 'slack' && <SlackGuideSection />}
          </>
        )}
      </div>
    </div>
  );
}
