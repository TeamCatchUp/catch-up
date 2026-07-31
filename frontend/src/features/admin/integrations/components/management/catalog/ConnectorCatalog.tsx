import { cn } from '@/shared/utils/cn';

import { CONNECTOR_CATEGORIES, CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';
import ConnectorCatalogCard from './ConnectorCatalogCard';
import ConnectorCatalogNotice from './ConnectorCatalogNotice';

const SERVICES = Object.keys(CONNECTOR_CONTENT) as IntegrationService[];

interface ConnectorCatalogProps {
  connectedServices: readonly IntegrationService[];
  /**
   * 카드 그리드 열 수.
   * 전폭(빈 상태)은 3열, 연동됨 목록이 있는 2단 배치의 우측 컬럼은 2열이다.
   * 컨테이너 폭으로 추론하지 않는다 — 부모가 이미 아는 정보다.
   */
  columns?: 2 | 3;
  onConnect: (service: IntegrationService) => void;
  onLearnMore: () => void;
}

/**
 * "연결 찾기" 카탈로그 — 카테고리 그룹 + 카드 그리드 + 하단 안내.
 * Figma `16922:134207`(3열) · `17125:115103`(2열).
 */
export default function ConnectorCatalog({
  connectedServices,
  columns = 3,
  onConnect,
  onLearnMore,
}: ConnectorCatalogProps) {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1">
        <h2 className="text-heading-large text-text-normal-normal">연결 찾기</h2>
        <p className="text-body-small text-text-normal-alternative">워크스페이스에서 사용 가능한 연결 살펴보기</p>
      </div>

      {CONNECTOR_CATEGORIES.map((category) => {
        const services = SERVICES.filter((service) => CONNECTOR_CONTENT[service].category === category);
        if (services.length === 0) return null;

        return (
          <section key={category} className="flex flex-col gap-3">
            <h3 className="text-body-small text-text-normal-alternative">{category}</h3>
            <div className={cn('grid gap-4', columns === 3 ? 'grid-cols-3' : 'grid-cols-2')}>
              {services.map((service) => (
                <ConnectorCatalogCard
                  key={service}
                  service={service}
                  connected={connectedServices.includes(service)}
                  onConnect={onConnect}
                />
              ))}
            </div>
          </section>
        );
      })}

      <ConnectorCatalogNotice onLearnMore={onLearnMore} />
    </div>
  );
}
