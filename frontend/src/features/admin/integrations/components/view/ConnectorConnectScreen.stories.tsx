'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { CONNECTOR_CONTENT } from '../../constants/connectorContent';
import { DEFAULT_PERIOD } from '../../constants/period';
import { useChannelTalkSelection } from '../../hooks/useChannelTalkSelection';
import type { ChannelTalkChannel } from '../../types/channelTalkModel';
import type { IntegrationService } from '../../types/integrationModel';
import ConnectorSummaryCard from '../management/cards/ConnectorSummaryCard';
import ConnectorCatalog from '../management/catalog/ConnectorCatalog';
import ChannelTalkChannelCard from '../management/channel-talk/ChannelTalkChannelCard';
import ChannelTalkFooterBar from '../management/channel-talk/ChannelTalkFooterBar';
import ChannelTalkStepper, { type ChannelTalkStep } from '../management/channel-talk/ChannelTalkStepper';
import ChannelTalkEmbeddingFooterBar from '../management/channel-talk/embedding/ChannelTalkEmbeddingFooterBar';
import ChannelTalkEmbeddingTargetPicker from '../management/channel-talk/embedding/ChannelTalkEmbeddingTargetPicker';
import ConnectorSidebarList, { type ConnectedConnector } from '../management/ConnectorSidebarList';
import ConnectorBackLink from '../management/detail/ConnectorBackLink';
import ConnectorDetailHeader from '../management/detail/ConnectorDetailHeader';
import ConnectorPreConnectDetail from '../management/detail/ConnectorPreConnectDetail';
import EmbeddedResourceTable from '../management/embedding/EmbeddedResourceTable';
import EmbeddingActiveTable from '../management/embedding/EmbeddingActiveTable';
import EmbeddingHistoryTable from '../management/embedding/EmbeddingHistoryTable';
import EmbeddingSegmentTabs, { type EmbeddingTabValue } from '../management/embedding/EmbeddingSegmentTabs';
import ConnectorEmptyState from '../management/states/ConnectorEmptyState';

/*
 * /admin/connectors 화면 스토리. Compositions를 실제 배선(ConnectorConnectView)과
 * 같은 셸 규칙으로 합쳐 화면 단위 상태를 보여준다 — 데이터 훅(useAdminIntegrationViewModel
 * 등)은 붙이지 않고 실측 응답을 fixture로 옮겼다(2026-08-04 스테이징 채널톡 계정).
 */

interface ConnectorScreenStoryArgs {
  onSelectConnector: (service: IntegrationService) => void;
  onStepChange: (step: ChannelTalkStep) => void;
  onExit: () => void;
}

/** 사이드바 "연동됨" 목록 — 스테이징 실측과 같은 5종 */
const SIDEBAR_FIXTURE: readonly ConnectedConnector[] = [
  { service: 'jira', workspaceName: 'example-workspace' },
  { service: 'github', workspaceName: 'TeamCatchUp' },
  { service: 'slack', workspaceName: 'CatchUp-캐치업' },
  { service: 'confluence', workspaceName: 'example-workspace' },
  { service: 'channel_talk', workspaceName: 'Catch Up | 캐치업' },
];

/** GET /admin/connector/status?source=channel_talk 실측 응답을 트리로 묶은 값 */
const RESOURCE_TREE_FIXTURE = [
  {
    id: '229395-229395',
    name: 'Catch Up | 캐치업',
    dataRange: '2026.04.15 - 2026.07.23',
    children: [
      { id: '229395-16957', name: 'Catch Up Guide', dataRange: '2026.04.30 - 2026.07.01' },
      { id: '229395-18234', name: '도큐먼트 스페이스 2', dataRange: '-' },
    ],
  },
] as const;

const HISTORY_FIXTURE = [
  { id: 'h-1', target: 'Catch Up | 캐치업', status: 'success' as const, executedAt: '2026.07.23 09:52 PM' },
  {
    id: 'h-2',
    target: 'Catch Up Guide',
    status: 'failed' as const,
    executedAt: '2026.07.01 11:10 AM',
    failureCount: 42,
  },
];

/** 스텝 ① 채널 폼 fixture — 테스트 완료라 collapsed lock 상태다 */
const CHANNEL_FORM_FIXTURE: ChannelTalkChannel = {
  id: 'ch-229395',
  name: 'Catch Up | 캐치업',
  accessKey: '',
  accessSecret: '',
  webhookToken: '',
  connectionStatus: 'tested',
  documentSpaces: [
    {
      id: 'ds-16957',
      name: 'Catch Up Guide',
      accessKey: '',
      accessSecret: '',
      syncInterval: '24hour',
      connectionStatus: 'tested',
    },
    {
      id: 'ds-18234',
      name: '도큐먼트 스페이스 2',
      accessKey: '',
      accessSecret: '',
      syncInterval: '24hour',
      connectionStatus: 'tested',
    },
  ],
};

/** 스텝 ② 선택기 fixture — sync targets 응답 모델(mapChannelTalkSyncTargets 출력형) */
const EMBED_CHANNELS_FIXTURE = [
  {
    channel_id: '229395',
    display_name: 'Catch Up | 캐치업',
    document_spaces: [
      { space_id: '16957', display_name: 'Catch Up Guide' },
      { space_id: '18234', display_name: '도큐먼트 스페이스 2' },
    ],
  },
];

/** ConnectorsPageClient의 셸 — 제목 블록 + gap 40 (Figma 17122:112580 공통 규칙) */
function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <section className="bg-background-normal-normal mx-auto flex w-full flex-col gap-10 px-16 pt-9 pb-30 min-[1440px]:max-w-292">
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-xlarge text-text-normal-normal">커넥터 연결</h1>
        <p className="text-body-small text-text-normal-alternative">CatchUp에서 사용하는 앱을 찾아 관리합니다.</p>
      </div>
      {children}
    </section>
  );
}

/**
 * ConnectorConnectView의 카드 셸 — 사이드바 260 + 우측 pane 하나의 테두리.
 * `paneOwnsPadding`은 채널톡 (F) 규칙 그대로다: 하단바가 pane 전폭을 써야 해서
 * pane padding을 콘텐츠 쪽으로 넘긴다.
 */
function CardShell({
  selected,
  paneOwnsPadding = false,
  onSelectConnector,
  children,
}: {
  selected: IntegrationService | null;
  paneOwnsPadding?: boolean;
  onSelectConnector: (service: IntegrationService) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border-line-normal-neutral flex overflow-hidden rounded-2xl border">
      <aside className="border-line-normal-neutral w-65 shrink-0 border-r p-3">
        <ConnectorSidebarList
          connectors={SIDEBAR_FIXTURE}
          selected={selected}
          onSelect={onSelectConnector}
          onAdd={() => onSelectConnector('jira')}
        />
      </aside>
      <div className={cn('min-w-0 flex-1', !paneOwnsPadding && 'px-8 py-6')}>{children}</div>
    </div>
  );
}

/** (E) 연동됨 상세 — 탭 전환은 화면 상태라 스토리가 직접 든다 */
function ConnectedDetailSurface({ onSelectConnector }: { onSelectConnector: (service: IntegrationService) => void }) {
  const [tab, setTab] = useState<EmbeddingTabValue>('manage');

  return (
    <PageShell>
      <CardShell selected="channel_talk" onSelectConnector={onSelectConnector}>
        <div className="flex flex-col gap-6">
          <ConnectorDetailHeader
            service="channel_talk"
            title="Catch Up | 캐치업"
            description={CONNECTOR_CONTENT.channel_talk.headerDescription}
            actions={
              <Button variant="box-solid-primary" size="lg">
                채널 연결하기
              </Button>
            }
          />
          <EmbeddingSegmentTabs value={tab} hasRunning onChange={setTab} />
          {tab === 'manage' ? (
            <div className="flex flex-col gap-6">
              <ConnectorSummaryCard connected dataRange="2026.04.15 - 2026.07.23" />
              <EmbeddedResourceTable service="channel_talk" label="연결된 채널톡 채널" rows={RESOURCE_TREE_FIXTURE} />
            </div>
          ) : (
            <div className="flex flex-col gap-8">
              <EmbeddingActiveTable service="channel_talk" items={[{ id: 't-1', target: 'Catch Up | 캐치업' }]} />
              <EmbeddingHistoryTable service="channel_talk" items={HISTORY_FIXTURE} onRetry={fn()} />
            </div>
          )}
        </div>
      </CardShell>
    </PageShell>
  );
}

/**
 * (D) 연동 전 상세 — ConnectorConnectView의 preconnect 분기와 같은 골격.
 * 사이드바 클릭으로 도구를 갈아끼워 커넥터별 카피(Confluence 확정본)를 훑는다.
 */
function PreConnectDetailSurface({
  initialService,
  onSelectConnector,
}: {
  initialService: IntegrationService;
  onSelectConnector: (service: IntegrationService) => void;
}) {
  const [service, setService] = useState<IntegrationService>(initialService);

  return (
    <PageShell>
      <CardShell
        selected={service}
        onSelectConnector={(next) => {
          setService(next);
          onSelectConnector(next);
        }}
      >
        <div className="flex flex-col gap-6">
          <ConnectorBackLink onBack={fn()} />
          <ConnectorPreConnectDetail service={service} onCheckMapping={fn()} onConnect={fn()} />
        </div>
      </CardShell>
    </PageShell>
  );
}

/**
 * (F) 채널톡 2스텝 — ChannelTalkFlowPanel과 같은 골격.
 * 콘텐츠(px-8)와 하단바가 형제라 하단바 경계선이 pane 전폭을 쓴다.
 */
function ChannelTalkFlowSurface({
  initialStep,
  onSelectConnector,
  onStepChange,
  onExit,
}: {
  initialStep: ChannelTalkStep;
  onSelectConnector: (service: IntegrationService) => void;
  onStepChange: (step: ChannelTalkStep) => void;
  onExit: () => void;
}) {
  const [step, setStep] = useState<ChannelTalkStep>(initialStep);
  const selection = useChannelTalkSelection(EMBED_CHANNELS_FIXTURE);

  const pickerChannels = EMBED_CHANNELS_FIXTURE.map((ch) => ({
    id: ch.channel_id,
    name: ch.display_name,
    dataRange: selection.channelPeriods[ch.channel_id] ?? DEFAULT_PERIOD,
    documentSpaces: ch.document_spaces.map((sp) => ({
      id: sp.space_id,
      name: sp.display_name,
      dataRange: selection.spacePeriods[sp.space_id] ?? DEFAULT_PERIOD,
    })),
  }));

  return (
    <PageShell>
      <CardShell selected="channel_talk" paneOwnsPadding onSelectConnector={onSelectConnector}>
        <div className="flex flex-col">
          <div className="flex flex-col gap-6 px-8 pt-6">
            <ConnectorDetailHeader
              service="channel_talk"
              title="Catch Up | 캐치업"
              description={CONNECTOR_CONTENT.channel_talk.headerDescription}
            />
            <ChannelTalkStepper
              current={step}
              onStepChange={(next) => {
                setStep(next);
                onStepChange(next);
              }}
              onBack={onExit}
            />
          </div>

          {step === 'connect' ? (
            <>
              <div className="flex flex-col gap-3 px-8 pt-6 pb-6">
                <ChannelTalkChannelCard
                  channel={CHANNEL_FORM_FIXTURE}
                  onUpdate={fn()}
                  onRemove={fn()}
                  onAddDocumentSpace={fn()}
                  onUpdateDocumentSpace={fn()}
                  onRemoveDocumentSpace={fn()}
                  onTestConnection={fn()}
                  onTestDocumentSpaceConnection={fn()}
                />
              </div>
              <ChannelTalkFooterBar
                channelCount={1}
                documentCount={2}
                onAddChannel={fn()}
                onProceed={() => setStep('embed')}
              />
            </>
          ) : (
            <>
              <div className="px-8 pt-6 pb-6">
                <ChannelTalkEmbeddingTargetPicker
                  channels={pickerChannels}
                  visibleChannelIds={selection.visibleChannelIds}
                  selectedChannelIds={selection.selectedChannelIds}
                  selectedDocumentIds={selection.selectedSpaceIds}
                  onToggleVisibility={selection.toggleVisibility}
                  onToggleChannel={selection.toggleChannel}
                  onToggleDocument={(_channelId, spaceId) => selection.toggleSpace(spaceId)}
                  onChannelDataRangeChange={(channelId, next) => selection.setChannelPeriod(channelId, next)}
                  onDocumentDataRangeChange={(_channelId, spaceId, next) => selection.setSpacePeriod(spaceId, next)}
                />
              </div>
              <ChannelTalkEmbeddingFooterBar
                channelCount={selection.channelCount}
                documentCount={selection.spaceCount}
                allSelected={selection.isAllSelected}
                onToggleAll={selection.toggleAll}
                onEmbed={fn()}
              />
            </>
          )}
        </div>
      </CardShell>
    </PageShell>
  );
}

const meta = {
  title: 'Screens/Admin/Connectors',
  tags: ['autodocs'],
  args: {
    onSelectConnector: fn(),
    onStepChange: fn(),
    onExit: fn(),
  },
  argTypes: {
    onSelectConnector: { control: false },
    onStepChange: { control: false },
    onExit: { control: false },
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: [
        'pre-connect-detail',
        'connected-detail',
        'channel-talk-step1',
        'channel-talk-step2',
        'catalog',
        'empty',
      ],
      dataNotes: [
        '사이드바·채널톡 fixture는 2026-08-04 스테이징 실측 응답(connector/status, connection-status)을 옮긴 값이다.',
        '데이터 훅은 붙이지 않는다 — 배선 검증은 프로덕션 빌드 Playwright가 담당하고, 여기는 화면 조립 규칙을 고정한다.',
      ],
      reuseNotes: [
        '셸 규칙은 ConnectorConnectView와 같다: 사이드바 260 + 우측 pane 한 테두리, 채널톡 (F)만 pane padding을 콘텐츠로 넘긴다.',
      ],
    }),
  },
} satisfies Meta<ConnectorScreenStoryArgs>;

export default meta;

type Story = StoryObj<ConnectorScreenStoryArgs>;

export const PreConnectDetail: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=16922-134092&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134092',
      },
      viewport: { width: 1440, height: 900 },
      states: ['jira', 'github', 'confluence', 'channel-talk'],
      dataNotes: [
        '카피는 Confluence "커넥터 연동 안내 문구"(CU, pageId 157941761) 확정본이다 — 사이드바 클릭으로 도구별 문구를 훑는다.',
      ],
    }),
  },
  render: (args) => <PreConnectDetailSurface initialService="jira" onSelectConnector={args.onSelectConnector} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('Jira — Confluence 확정 카피', async () => {
      await expect(canvas.getByText(/완료된 이슈는 누구도 다시 열어보지 않아요/)).toBeInTheDocument();
      await expect(canvas.getByText('"이 기능 왜 보류됐었지?"')).toBeInTheDocument();
    });

    await step('사이드바 Github 클릭 → Github 카피', async () => {
      await userEvent.click(canvas.getByRole('button', { name: /Github - TeamCatchUp/ }));
      await expect(args.onSelectConnector).toHaveBeenCalledWith('github');
      await expect(canvas.getByText(/코드에는 "왜"가 없습니다/)).toBeInTheDocument();
      await expect(canvas.getByText('코드 수정과 푸시 — 읽기 전용으로만 동작해요')).toBeInTheDocument();
    });
  },
};

export const ConnectedDetail: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=17306-82016&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17306:82016',
      },
      viewport: { width: 1440, height: 900 },
      states: ['manage-tab', 'status-tab'],
      layoutNotes: ['임베딩 관리 탭: 요약 카드 + 채널→도큐먼트 2단 계층 표. 현황 탭: 진행중 + 히스토리.'],
    }),
  },
  render: (args) => <ConnectedDetailSurface onSelectConnector={args.onSelectConnector} />,
  play: async ({ canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('관리 탭 — 채널톡 계층이 나온다', async () => {
      await expect(canvas.getByText('Catch Up Guide')).toBeInTheDocument();
      await expect(canvas.getByText('도큐먼트 스페이스 2')).toBeInTheDocument();
    });

    await step('현황 탭 전환 — 진행중·히스토리 표', async () => {
      await userEvent.click(canvas.getByRole('tab', { name: /임베딩 현황/ }));
      await expect(canvas.getByText('임베딩 히스토리')).toBeInTheDocument();
      await expect(canvas.getByText('2026.07.23 09:52 PM')).toBeInTheDocument();
    });
  },
};

export const ChannelTalkStep1: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=17332-84379&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17332:84379',
      },
      viewport: { width: 1440, height: 900 },
      states: ['step1-tested-collapsed'],
      layoutNotes: ['하단바는 콘텐츠(px-8)의 형제라 위 경계선이 pane 전폭을 쓴다.'],
    }),
  },
  render: (args) => (
    <ChannelTalkFlowSurface
      initialStep="connect"
      onSelectConnector={args.onSelectConnector}
      onStepChange={args.onStepChange}
      onExit={args.onExit}
    />
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('스텝 ① — 테스트 완료 채널 카드', async () => {
      await expect(canvas.getAllByText('테스트 완료')).toHaveLength(3);
    });

    await step('스텝퍼 ② 칩 클릭 → 선택기로 전환', async () => {
      // '임베딩하기'는 스텝퍼 칩과 하단 바 버튼 두 곳이다 — DOM 순서상 첫 번째가 칩
      await userEvent.click(canvas.getAllByRole('button', { name: '임베딩하기' })[0]);
      await expect(args.onStepChange).toHaveBeenCalledWith('embed');
      await expect(canvas.getByText('전체 선택하기')).toBeInTheDocument();
    });
  },
};

export const ChannelTalkStep2: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=17414-97603&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17414:97603',
      },
      viewport: { width: 1440, height: 900 },
      states: ['step2-picker', 'step2-all-selected'],
      interactionNotes: ['선택 시맨틱은 useChannelTalkSelection 실제 훅이다 — 전체 선택 시 임베딩하기가 활성화된다.'],
    }),
  },
  render: (args) => (
    <ChannelTalkFlowSurface
      initialStep="embed"
      onSelectConnector={args.onSelectConnector}
      onStepChange={args.onStepChange}
      onExit={args.onExit}
    />
  ),
  play: async ({ canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    // '임베딩하기'는 스텝퍼 칩에도 있다 — 하단 바 버튼은 DOM 마지막
    const embedButton = () => canvas.getAllByRole('button', { name: '임베딩하기' }).at(-1) as HTMLElement;

    await step('선택 0개 — 임베딩하기 비활성', async () => {
      await expect(embedButton()).toBeDisabled();
    });

    await step('전체 선택 → 임베딩하기 활성', async () => {
      await userEvent.click(canvas.getByRole('checkbox', { name: '전체 선택하기' }));
      await expect(embedButton()).toBeEnabled();
    });
  },
};

export const Catalog: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=17125-115103&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17125:115103',
      },
      viewport: { width: 1440, height: 900 },
      states: ['catalog-all-connected'],
    }),
  },
  render: (args) => (
    <PageShell>
      <CardShell selected={null} onSelectConnector={args.onSelectConnector}>
        <ConnectorCatalog
          connectedServices={SIDEBAR_FIXTURE.map((item) => item.service)}
          onConnect={args.onSelectConnector}
          onLearnMore={fn()}
        />
      </CardShell>
    </PageShell>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('커넥터 추가하기')).toBeInTheDocument();
  },
};

export const Empty: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=17122-112581&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17122:112581',
      },
      viewport: { width: 1440, height: 900 },
      states: ['empty'],
      layoutNotes: ['연동 0개 — 사이드바 없이 자체 테두리 카드 하나다.'],
    }),
  },
  render: () => (
    <PageShell>
      <ConnectorEmptyState onStart={fn()} />
    </PageShell>
  ),
};
