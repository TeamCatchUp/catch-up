'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { API } from '@/shared/api/endpoints';

import { CONNECTOR_CONTENT } from '../../constants/connectorContent';
import { useAdminIntegrationViewModel } from '../../hooks/useAdminIntegrationViewModel';
import type { IntegrationService } from '../../types/integrationModel';
import ConnectorCatalog from '../management/catalog/ConnectorCatalog';
import ChannelTalkFlowPanel from '../management/channel-talk/ChannelTalkFlowPanel';
import type { ChannelTalkStep } from '../management/channel-talk/ChannelTalkStepper';
import ConnectorSidebarList from '../management/ConnectorSidebarList';
import ConnectorBackLink from '../management/detail/ConnectorBackLink';
import ConnectorConnectedDetail from '../management/detail/ConnectorConnectedDetail';
import ConnectorPreConnectDetail from '../management/detail/ConnectorPreConnectDetail';
import ConnectorEmptyState from '../management/states/ConnectorEmptyState';
import ConnectorStateBoundary from '../management/states/ConnectorStateBoundary';

/** 서비스별 OAuth 이탈 — 구 IntegrationManagementSection의 핸들러를 옮겼다 */
const startOAuth = (service: IntegrationService) => {
  switch (service) {
    case 'slack':
      window.location.href = API.slack.install;
      break;
    case 'jira':
    case 'confluence':
      window.location.href = API.atlassian.install;
      break;
    case 'github':
      // 현행에도 Github 설치 진입이 없다 — 연동 안내만 제공(카탈로그 유지)
      break;
    case 'channel_talk':
      // OAuth가 없다 — 호출부에서 (F)로 전환한다
      break;
  }
};

type ViewState =
  | { kind: 'catalog' }
  | { kind: 'preconnect'; service: IntegrationService }
  | { kind: 'detail'; service: IntegrationService }
  | { kind: 'channelTalkFlow'; step: ChannelTalkStep };

/**
 * /admin/connectors 화면 상태 기계. 스펙 §5-1.
 *
 * 연동 0개: 사이드바 없음 — (A) 빈 상태 → (B) 카탈로그 전폭(3열).
 * 연동 ≥1: 좌측 목록 + 우측 교체 — (B') 카탈로그 2열 / (D) 연동 전 상세 /
 * (E) 연동됨 상세 / (F) 채널톡 2스텝. 목록과 추가하기는 정확히 하나만 selected.
 */
export default function ConnectorConnectView() {
  const router = useRouter();
  const { integrationMenu, getConnectorDetail } = useAdminIntegrationViewModel();

  const connectedMenu = integrationMenu.filter((item) => item.connected);
  const hasConnected = connectedMenu.length > 0;

  // (A)와 (B)를 가르는 진입 플래그 — 빈 상태에서 [커넥터 연결하기]를 눌러야 카탈로그
  const [entered, setEntered] = useState(false);
  const [state, setState] = useState<ViewState | null>(null);

  // 초기 화면: 연동 1개 이상이면 첫 연동 커넥터 상세, 0개면 카탈로그(빈 상태 뒤)
  const resolved: ViewState =
    state ?? (hasConnected ? { kind: 'detail', service: connectedMenu[0].service } : { kind: 'catalog' });

  const goCheckMapping = () => router.push('/admin/user-mapping');

  const handleConnect = (service: IntegrationService) => {
    setState({ kind: 'preconnect', service });
  };

  const handlePreConnectProceed = (service: IntegrationService) => {
    if (service === 'channel_talk') setState({ kind: 'channelTalkFlow', step: 'connect' });
    else startOAuth(service);
  };

  const rightPane = (() => {
    switch (resolved.kind) {
      case 'catalog':
        // 안내 배너는 ConnectorCatalog가 내부에서 렌더한다 — 여기서 또 붙이면 중복
        return (
          <ConnectorCatalog
            connectedServices={connectedMenu.map((item) => item.service)}
            columns={hasConnected ? 2 : 3}
            onConnect={handleConnect}
            onLearnMore={goCheckMapping}
          />
        );
      case 'preconnect': {
        const detail = getConnectorDetail(resolved.service);
        return (
          <div className="flex flex-col gap-6">
            <ConnectorBackLink onBack={() => setState({ kind: 'catalog' })} />
            <ConnectorStateBoundary status={detail.status} serviceName={CONNECTOR_CONTENT[resolved.service].name}>
              <ConnectorPreConnectDetail
                service={resolved.service}
                onCheckMapping={goCheckMapping}
                onConnect={() => handlePreConnectProceed(resolved.service)}
              />
            </ConnectorStateBoundary>
          </div>
        );
      }
      case 'detail': {
        const detail = getConnectorDetail(resolved.service);
        return (
          <ConnectorStateBoundary status={detail.status} serviceName={CONNECTOR_CONTENT[resolved.service].name}>
            <ConnectorConnectedDetail
              service={resolved.service}
              detail={detail}
              onEnterChannelTalkFlow={() => setState({ kind: 'channelTalkFlow', step: 'embed' })}
            />
          </ConnectorStateBoundary>
        );
      }
      case 'channelTalkFlow':
        return (
          <ChannelTalkFlowPanel
            initialStep={resolved.step}
            onExit={() => setState({ kind: 'detail', service: 'channel_talk' })}
          />
        );
    }
  })();

  // (A) 빈 상태 — 연동 0개 + 카탈로그 진입 전. 자체 테두리 카드라 셸을 덧씌우지 않는다
  if (!hasConnected && !entered && state === null) {
    return <ConnectorEmptyState onStart={() => setEntered(true)} />;
  }

  // 연동 0개 — 사이드바 없이 테두리 카드 하나 (Figma `17122:112581` 우측 padding 규칙 동일)
  if (!hasConnected) {
    return <div className="border-line-normal-neutral rounded-2xl border px-8 py-6">{rightPane}</div>;
  }

  /*
   * 연동 ≥1 — 사이드바 260 + 우측을 **하나의 테두리**로 감싼다.
   * Figma `17125:115106`·`17169:74058`: 바깥 radius 16 + `line/normal/neutral` 1px,
   * 두 단 사이 gap 0(사이드바의 오른쪽 경계선이 구분), 사이드바 padding 12,
   * 우측 padding 24/32 → 콘텐츠 716.
   * 사이드바는 고정 260, 우측이 남은 폭을 먹는다.
   */
  return (
    <div className="border-line-normal-neutral flex overflow-hidden rounded-2xl border">
      <aside className="border-line-normal-neutral w-65 shrink-0 border-r p-3">
        <ConnectorSidebarList
          connectors={connectedMenu.map((item) => ({
            service: item.service,
            // 워크스페이스명은 API가 아직 주지 않는다 — 도구명으로 대신한다(미결)
            workspaceName: CONNECTOR_CONTENT[item.service].name,
          }))}
          selected={
            resolved.kind === 'preconnect' || resolved.kind === 'detail'
              ? resolved.service
              : resolved.kind === 'channelTalkFlow'
                ? 'channel_talk'
                : null
          }
          onSelect={(service) => setState({ kind: 'detail', service })}
          onAdd={() => setState({ kind: 'catalog' })}
        />
      </aside>
      <div className="min-w-0 flex-1 px-8 py-6">{rightPane}</div>
    </div>
  );
}
