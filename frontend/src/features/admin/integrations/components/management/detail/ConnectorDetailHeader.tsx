import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';

interface ConnectorDetailHeaderProps {
  service: IntegrationService;
  /** 연동 전에는 도구명, 연동 후에는 워크스페이스명이 온다 */
  title: string;
  description: string;
  /** 우측 액션. 연동 전은 매핑 확인하기 + 연결하기, 연동됨은 임베딩 추가 */
  actions?: React.ReactNode;
}

/**
 * 커넥터 상세 헤더.
 * 연동 전·연동됨 두 상태가 같은 헤더를 쓰고 액션만 바뀐다.
 */
export default function ConnectorDetailHeader({ service, title, description, actions }: ConnectorDetailHeaderProps) {
  const Logo = CONNECTOR_LOGOS[service];

  return (
    <div className="flex items-center gap-4">
      <div className="bg-fill-normal-strong flex size-15 shrink-0 items-center justify-center rounded-xl">
        <Logo className="size-11" />
      </div>

      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
        <h2 className="text-heading-large text-text-normal-normal truncate">{title}</h2>
        <p className="text-body-small text-text-normal-alternative truncate">{description}</p>
      </div>

      {actions && <div className="flex shrink-0 items-center gap-2.5">{actions}</div>}
    </div>
  );
}
