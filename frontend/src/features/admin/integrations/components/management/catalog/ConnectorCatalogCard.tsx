import IconCheck from '@/public/icons/icon/check.svg';
import { Button } from '@/shared/components/ui/button';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';

interface ConnectorCatalogCardProps {
  service: IntegrationService;
  /** 이미 연결된 도구는 버튼이 "연결됨" 비활성으로 남는다 */
  connected: boolean;
  onConnect: (service: IntegrationService) => void;
}

/**
 * 카탈로그의 커넥터 카드 1장.
 */
export default function ConnectorCatalogCard({ service, connected, onConnect }: ConnectorCatalogCardProps) {
  const content = CONNECTOR_CONTENT[service];
  const Logo = CONNECTOR_LOGOS[service];

  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-3 rounded-xl border p-4">
      <div className="flex items-center gap-3">
        <div className="bg-fill-normal-strong flex size-10 shrink-0 items-center justify-center rounded-lg">
          <Logo className="size-7" />
        </div>
        <span className="text-body-medium text-text-normal-normal min-w-0 flex-1 truncate">{content.name}</span>
        {connected ? (
          <Button variant="box-outline-gray" size="sm" disabled>
            연결됨
            <IconCheck className="size-4" />
          </Button>
        ) : (
          <Button variant="box-outline-gray" size="sm" onClick={() => onConnect(service)}>
            연결
          </Button>
        )}
      </div>
      <span className="text-body-small text-text-normal-alternative truncate">{content.catalogDescription}</span>
    </div>
  );
}
