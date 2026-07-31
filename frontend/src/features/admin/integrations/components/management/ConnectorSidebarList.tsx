import IconAddSmall from '@/public/icons/icon/add_small.svg';
import SnbMenuItem from '@/shared/components/layout/panels/SnbMenuItem';

import { CONNECTOR_CONTENT } from '../../constants/connectorContent';
import { CONNECTOR_LOGOS } from '../../constants/connectorLogos';
import type { IntegrationService } from '../../types/integrationModel';

export interface ConnectedConnector {
  service: IntegrationService;
  /** 외부 워크스페이스 이름. "Slack - 워크스페이스명" 형태로 이어 붙인다 */
  workspaceName: string;
}

interface ConnectorSidebarListProps {
  connectors: readonly ConnectedConnector[];
  /** null이면 "커넥터 추가하기"가 선택된 상태다 */
  selected: IntegrationService | null;
  onSelect: (service: IntegrationService) => void;
  onAdd: () => void;
}

/**
 * 좌측 "연동됨" 커넥터 목록.
 * Figma `17125:115103` — 항목은 설정 사이드바와 같은 `SNB/menu`다.
 * 추가하기와 커넥터 항목을 통틀어 정확히 하나만 selected다.
 */
export default function ConnectorSidebarList({ connectors, selected, onSelect, onAdd }: ConnectorSidebarListProps) {
  return (
    <div className="flex flex-col gap-6">
      <SnbMenuItem Icon={IconAddSmall} label="커넥터 추가하기" selected={selected === null} onClick={onAdd} />

      <div className="flex flex-col gap-2">
        <span className="text-body-small text-text-normal-alternative px-2.5">연동됨</span>
        <div className="flex flex-col gap-1">
          {connectors.map(({ service, workspaceName }) => (
            <SnbMenuItem
              key={service}
              Icon={CONNECTOR_LOGOS[service]}
              label={`${CONNECTOR_CONTENT[service].name} - ${workspaceName}`}
              selected={selected === service}
              onClick={() => onSelect(service)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
