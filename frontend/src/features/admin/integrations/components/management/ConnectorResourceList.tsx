import { useState } from 'react';

import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconGithubLogo from '@/public/icons/logo/GitHub.svg';
import Pagination from '@/shared/components/ui/pagination';

import { RESOURCES_PER_PAGE } from '../../constants/integrationsConfig';
import type { ConnectorResource, IntegrationService } from '../../types/integrationModel';

/** 서비스별 리소스 아이템 아이콘 */
const RESOURCE_ICONS: Record<IntegrationService, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  jira: IconSpace,
  github: IconGithubLogo,
  slack: IconTag,
  confluence: IconSpace,
  channel_talk: IconTag,
};

interface ConnectorResourceListProps {
  service: IntegrationService;
  resourceLabel: string;
  resources: ConnectorResource[];
}

/** 임베딩된 리소스 목록 + 페이지네이션. IntegrationManagementSection에서 추출했다 — 동작 변경 없음. */
export default function ConnectorResourceList({ service, resourceLabel, resources }: ConnectorResourceListProps) {
  const [currentPage, setCurrentPage] = useState(1);

  // 서비스 변경 시 페이지 리셋 — 렌더 중 조정 (useEffect 이중 렌더 방지)
  const [prevService, setPrevService] = useState(service);
  if (prevService !== service) {
    setPrevService(service);
    setCurrentPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(resources.length / RESOURCES_PER_PAGE));
  const paginatedResources = resources.slice((currentPage - 1) * RESOURCES_PER_PAGE, currentPage * RESOURCES_PER_PAGE);
  const ResourceIcon = RESOURCE_ICONS[service];

  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-text-normal-neutral">{resourceLabel}</h3>
      <div className="border-line-normal-assistive bg-fill-normal-strong flex flex-col items-center gap-3 overflow-hidden rounded-xl border pt-2 pb-3">
        {resources.length > 0 ? (
          <>
            <div className="flex w-full flex-col">
              {paginatedResources.map((row, index) => (
                <div
                  key={`${row.name}-${index}`}
                  className="text-body-small text-text-normal-neutral flex h-13 items-center gap-3 px-4 py-3"
                >
                  <div className="border-line-normal-neutral bg-fill-normal-normal/75 flex shrink-0 items-center justify-center overflow-hidden rounded-full border p-1.5">
                    <ResourceIcon className="size-5" />
                  </div>
                  <span className="flex-1 truncate">{row.name}</span>
                  {row.dateRange && row.dateRange !== '-' && (
                    <span className="text-label-xsmall text-text-normal-neutral shrink-0 whitespace-nowrap">
                      {row.dateRange}
                    </span>
                  )}
                </div>
              ))}
            </div>
            {totalPages > 1 && (
              <>
                <div className="w-full px-4">
                  <div className="border-line-normal-neutral border-t" />
                </div>
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
              </>
            )}
          </>
        ) : (
          <div className="text-body-small text-text-normal-assistive flex h-13 items-center px-4 py-3">
            연동된 항목이 없습니다.
          </div>
        )}
      </div>
    </div>
  );
}
