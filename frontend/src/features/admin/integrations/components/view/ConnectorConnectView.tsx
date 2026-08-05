'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { API } from '@/shared/api/endpoints';
import { cn } from '@/shared/utils/cn';

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
import ConnectorDetailSkeleton from '../management/states/ConnectorDetailSkeleton';
import ConnectorEmptyState from '../management/states/ConnectorEmptyState';
import ConnectorErrorNotice from '../management/states/ConnectorErrorNotice';
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
      // 도달하지 않는다 — (D)가 github의 [연결하기]를 숨긴다(가이드로 직접 설치 안내)
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

  const goCheckMapping = () => router.push('/mypage/help/support/2');

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
              // 헤더 액션이 "채널 연결하기"라 스텝 ①로 들어간다 — 채널 등록이 임베딩보다 선행이다
              onEnterChannelTalkFlow={() => setState({ kind: 'channelTalkFlow', step: 'connect' })}
            />
          </ConnectorStateBoundary>
        );
      }
      case 'channelTalkFlow':
        return (
          <ChannelTalkFlowPanel
            initialStep={resolved.step}
            workspaceName={connectedMenu.find((item) => item.service === 'channel_talk')?.workspaceName ?? null}
            onExit={() => setState({ kind: 'detail', service: 'channel_talk' })}
          />
        );
    }
  })();

  // 채널톡 (F)만 하단 바 경계선이 pane 전폭을 써야 해서 padding을 패널 스스로 갖는다
  const paneOwnsPadding = resolved.kind === 'channelTalkFlow';

  /*
   * 부트스트랩 — connection-status 쿼리가 아직이면 hasConnected가 false라
   * 빈 상태가 번쩍 나타난다. 판정 전에는 스켈레톤을 깔고, 하나라도 실패했으면
   * 연동 여부를 모르는 상태이므로 빈 상태 대신 오류를 알린다(resolveConnectorStatus의
   * error > loading > ready 우선순위와 같은 규칙).
   */
  if (!hasConnected && integrationMenu.some((item) => item.status === 'error')) {
    return <ConnectorErrorNotice serviceName="커넥터" />;
  }
  if (!hasConnected && integrationMenu.some((item) => item.status === 'loading')) {
    return <ConnectorDetailSkeleton />;
  }

  // (A) 빈 상태 — 연동 0개 + 카탈로그 진입 전. 자체 테두리 카드라 셸을 덧씌우지 않는다
  if (!hasConnected && !entered && state === null) {
    return <ConnectorEmptyState onStart={() => setEntered(true)} />;
  }

  // 연동 0개 — 사이드바 없이 테두리 카드 하나
  if (!hasConnected) {
    return (
      <div
        className={cn('border-line-normal-neutral overflow-hidden rounded-2xl border', !paneOwnsPadding && 'px-8 py-6')}
      >
        {rightPane}
      </div>
    );
  }

  // 연동 ≥1 — 고정 폭 사이드바 + 우측 pane을 하나의 테두리로 감싼다. 구분선은 사이드바의 오른쪽 경계선
  return (
    <div className="border-line-normal-neutral flex overflow-hidden rounded-2xl border">
      <aside className="border-line-normal-neutral w-65 shrink-0 border-r p-3">
        <ConnectorSidebarList
          connectors={connectedMenu.map((item) => ({
            service: item.service,
            // connection-status items[].name. 백엔드가 null을 주면 도구명으로 폴백한다
            workspaceName: item.workspaceName ?? CONNECTOR_CONTENT[item.service].name,
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
      <div className={cn('min-w-0 flex-1', !paneOwnsPadding && 'px-8 py-6')}>{rightPane}</div>
    </div>
  );
}
