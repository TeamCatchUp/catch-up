import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconGithubLogo from '@/public/icons/logo/GitHub.svg';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import Pagination from '@/shared/components/ui/pagination';
import { cn } from '@/shared/utils/cn';

import { RESOURCES_PER_PAGE } from '../../constants/integrations';
import type { ConnectorDetail, IntegrationMenuItem, IntegrationService } from '../../types/integrations';
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
};

const GITHUB_APP_URL = 'https://github.com/apps/catchupqa';

/** 서비스별 연동 설치 핸들러 */
const handleInstall = (service: IntegrationService) => {
  switch (service) {
    case 'github':
      window.open(GITHUB_APP_URL, '_blank');
      break;
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
const IntegrationManagementSection = ({
  integrationMenu,
  selectedService,
  onSelectService,
  detail,
}: IntegrationManagementSectionProps) => {
  const [currentPage, setCurrentPage] = useState(1);

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

  const syncMutation = useMutation({
    mutationKey: ['admin', 'connector', 'sync', selectedService] as const,
    mutationFn: async () => {
      switch (selectedService) {
        case 'github':
          return api.post(API.github.syncFlush);
        case 'jira':
          return api.post(API.jira.syncFlush);
        case 'slack':
          return api.post(API.slack.syncFlush);
        case 'confluence': {
          const { data } = await api.get<{ cloudIds: string[] }>(API.confluence.cloudIds);
          await Promise.all(
            data.cloudIds.map((cloudId) =>
              api.post(API.confluence.syncIncremental, null, { params: { cloud_id: cloudId } }),
            ),
          );
          return;
        }
      }
    },
  });

  return (
    <div className="flex gap-8">
      <div className="flex w-81.25 flex-col gap-4">
        {integrationMenu.map(({ service, Icon, actionText, connected }) => {
          const isSelected = selectedService === service;

          return (
            <button
              key={service}
              type="button"
              onClick={() => onSelectService(service)}
              className={cn(
                'flex h-16 w-81.25 cursor-pointer items-center justify-between rounded-xl border p-4 shadow-[0_0_4px_0_#f7fbff]',
                isSelected ? 'border-blue-30 bg-white' : 'border-neutral-3 bg-white',
              )}
            >
              <div className="flex items-center gap-3">
                <Icon className={service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0'} />
                <span className="text-heading-small text-gray-80">{actionText}</span>
              </div>
              <div className="flex items-center gap-1">
                {connected ? (
                  <>
                    <IconCloudCheckFilled className="h-5 w-5 text-blue-50" />
                    <span className="text-body-xsmall text-blue-50">연동됨</span>
                  </>
                ) : (
                  <>
                    <IconCloudOff className="text-gray-30 h-5 w-5" />
                    <span className="text-body-xsmall text-gray-50">연동 안됨</span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex w-160.75 flex-none flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-5">
            <h3 className="text-heading-small text-gray-80 flex-1">연동 상태 관리</h3>
            <div className="flex shrink-0 items-center gap-3">
              <button
                type="button"
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="border-neutral-3 text-body-xsmall text-gray-70 flex h-7.5 min-w-7.5 cursor-pointer items-center justify-center gap-1 rounded-lg border bg-white px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <IconRotate className="text-gray-70 h-6 w-6" />
                {syncMutation.isPending ? '동기화 중...' : '동기화'}
              </button>
            </div>
          </div>
          <div className="border-neutral-3 bg-neutral-1 overflow-hidden rounded-xl border">
            <div className="border-neutral-3 flex h-13 items-center justify-between border-b px-4 py-3">
              <span className="text-body-small text-gray-70">연동 상태</span>
              <div className="flex items-center gap-1">
                {detail.connected ? (
                  <span className="text-body-xsmall text-blue-50">연동됨</span>
                ) : (
                  <>
                    <div className="flex items-center gap-1 px-1.5 py-1">
                      <IconCloudOff className="text-gray-20 size-5" />
                      <span className="text-body-xsmall text-gray-50">연동 안됨</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleInstall(selectedService)}
                      className="text-body-xsmall cursor-pointer rounded-full px-1.5 py-1 text-blue-50"
                    >
                      연동하기
                    </button>
                  </>
                )}
              </div>
            </div>
            <div className="border-neutral-3 flex h-13 items-center justify-between border-b px-4 py-3">
              <span className="text-body-small text-gray-70">보안 관련 설명</span>
              <button
                type="button"
                className="text-body-xsmall text-gray-70 flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1"
              >
                원문 보기
                <IconOpenInNew className="h-4.5 w-4.5" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-small text-gray-70">연동된 데이터 범위</h3>
          <div className="border-neutral-3 bg-neutral-1 text-body-small text-gray-70 flex h-10.75 items-center justify-center rounded-xl border px-5">
            {detail.dataRange}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-small text-gray-70">{detail.resourceLabel}</h3>
          <div className="border-neutral-3 bg-neutral-1 flex flex-col items-center gap-3 overflow-hidden rounded-xl border pt-2 pb-3">
            {detail.resources.length > 0 ? (
              <>
                <div className="flex w-full flex-col">
                  {paginatedResources.map((row, index) => {
                    const ResourceIcon = RESOURCE_ICONS[selectedService];
                    return (
                      <div
                        key={`${row}-${index}`}
                        className="text-body-small text-gray-70 flex h-13 items-center gap-3 px-4 py-3"
                      >
                        <div className="border-neutral-3 flex shrink-0 items-center justify-center overflow-hidden rounded-full border bg-white/75 p-1.5">
                          <ResourceIcon className="size-5" />
                        </div>
                        <span className="truncate">{row}</span>
                      </div>
                    );
                  })}
                </div>
                {totalPages > 1 && (
                  <>
                    <div className="w-full px-4">
                      <div className="border-neutral-3 border-t" />
                    </div>
                    <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
                  </>
                )}
              </>
            ) : (
              <div className="text-body-small text-gray-40 flex h-13 items-center px-4 py-3">
                연동된 항목이 없습니다.
              </div>
            )}
          </div>
        </div>

        {selectedService === 'jira' && <JiraGuideSection />}
        {selectedService === 'confluence' && <ConfluenceGuideSection />}
        {selectedService === 'github' && <GithubGuideSection />}
        {selectedService === 'slack' && <SlackGuideSection />}
      </div>
    </div>
  );
};

export default IntegrationManagementSection;
