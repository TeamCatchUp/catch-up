import { CONNECTOR_CATEGORIES, CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';
import ConnectorCatalogCard from './ConnectorCatalogCard';
import ConnectorCatalogNotice from './ConnectorCatalogNotice';

const SERVICES = Object.keys(CONNECTOR_CONTENT) as IntegrationService[];

interface ConnectorCatalogProps {
  connectedServices: readonly IntegrationService[];
  onConnect: (service: IntegrationService) => void;
  onLearnMore: () => void;
}

/**
 * "연결 찾기" 카탈로그 — 카테고리 그룹 + 카드 그리드 + 하단 안내.
 */
export default function ConnectorCatalog({ connectedServices, onConnect, onLearnMore }: ConnectorCatalogProps) {
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
            {/*
              * 열 수를 박지 않는다 — auto-fill이라 설계 폭에서는 Figma의 열 수가
              * 그대로 나오고, 그보다 좁으면 열이 줄어 카드가 찌그러지지 않는다.
              */}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
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
