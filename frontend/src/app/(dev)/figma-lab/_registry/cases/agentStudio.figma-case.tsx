import { useState } from 'react';

import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';
import LabIcon from '@/public/icons/icon/lab.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';
import type { AgentStudioCardModel, AgentStudioFilter } from '@/features/agent-studio/types/agentStudioModel';
import AgentCard from '@/features/agent-studio/components/list/AgentCard';
import AgentEmptyColumn from '@/features/agent-studio/components/list/AgentEmptyColumn';
import AgentFilterTabs from '@/features/agent-studio/components/list/AgentFilterTabs';
import AgentStatusSection from '@/features/agent-studio/components/list/AgentStatusSection';
import AgentStudioHeader from '@/features/agent-studio/components/list/AgentStudioHeader';
import AgentStudioEditorPage from '@/features/agent-studio/components/editor/AgentStudioEditorPage';
import {
  AGENT_STUDIO_FILTERS,
  AGENT_STUDIO_LIST_FIXTURE,
  AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE,
} from '@/features/agent-studio/fixtures/agentStudioFixtures';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';

const ACTIVE_EMPTY_STATE = {
  title: '운영 중인 Agent가 없습니다.',
  description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
} as const;

const DRAFT_EMPTY_STATE = {
  title: '제작 중인 Agent가 없습니다.',
  description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
} as const;

const INACTIVE_EMPTY_STATE = {
  title: '아직 비활성 Agent가 없습니다.',
  description: '사용을 중지한 Agent는 이곳에 보관됩니다.',
} as const;

function getVisibleAgents(agents: readonly AgentStudioCardModel[], filter: AgentStudioFilter) {
  if (filter === 'all') return agents;
  return agents.filter((item) => item.status === filter);
}

function AgentStudioListFixturePreview() {
  const [selectedFilter, setSelectedFilter] = useState<AgentStudioFilter>('all');
  const [agents, setAgents] = useState<readonly AgentStudioCardModel[]>(AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE);
  const visibleAgents = getVisibleAgents(agents, selectedFilter);
  const activeAgents = visibleAgents.filter((agent) => agent.status === 'active');
  const draftAgents = visibleAgents.filter((agent) => agent.status === 'draft');
  const inactiveAgents = visibleAgents.filter((agent) => agent.status === 'inactive');
  const isGroupedView = selectedFilter === 'all';
  const cardLayout = isGroupedView ? 'grouped' : 'flat';
  const shouldShowActiveEmpty = activeAgents.length === 0 && (selectedFilter === 'all' || selectedFilter === 'active');
  const shouldShowDraftEmpty = draftAgents.length === 0 && (selectedFilter === 'all' || selectedFilter === 'draft');
  const shouldShowInactiveEmpty =
    inactiveAgents.length === 0 && (selectedFilter === 'all' || selectedFilter === 'inactive');

  const updateStatus = (agentId: string, status: AgentStudioCardModel['status']) => {
    setAgents((current) => current.map((item) => (item.id === agentId ? { ...item, status } : item)));
  };

  return (
    <div className="bg-background-normal-normal flex min-h-full flex-col">
      <AgentStudioHeader />
      <section className="flex flex-col items-center gap-3 px-16 pt-6 pb-30">
        <h1 className="text-heading-large text-text-normal-normal w-full">우리 팀의 Agent</h1>
        <div className="flex w-full items-center gap-5">
          <AgentFilterTabs filters={AGENT_STUDIO_FILTERS} selected={selectedFilter} onChange={setSelectedFilter} />
          <Button variant="box-solid-primary" size="md">
            <LabIcon className="size-5" aria-hidden="true" />
            Agent 만들기
          </Button>
        </div>
        <div className={cn('flex w-full flex-wrap items-start gap-6', !isGroupedView && 'min-h-52.75')}>
          {isGroupedView ? (
            <>
              {activeAgents.length > 0 ? (
                <AgentStatusSection label="운영중" className="min-h-70.75">
                  <div className="flex w-full flex-col gap-3">
                    {activeAgents.map((agent) => (
                      <AgentCard
                        key={agent.id}
                        agent={agent}
                        layout="grouped"
                        onDeactivate={(target) => updateStatus(target.id, 'inactive')}
                      />
                    ))}
                  </div>
                </AgentStatusSection>
              ) : (
                <AgentEmptyColumn
                  label="운영중"
                  title={ACTIVE_EMPTY_STATE.title}
                  description={ACTIVE_EMPTY_STATE.description}
                />
              )}
              {draftAgents.length > 0 ? (
                <AgentStatusSection label="제작중" className="min-h-70.75">
                  <div className="flex w-full flex-col gap-3">
                    {draftAgents.map((agent) => (
                      <AgentCard
                        key={agent.id}
                        agent={agent}
                        layout="grouped"
                        onDeactivate={(target) => updateStatus(target.id, 'inactive')}
                      />
                    ))}
                  </div>
                </AgentStatusSection>
              ) : (
                <AgentEmptyColumn
                  label="제작중"
                  title={DRAFT_EMPTY_STATE.title}
                  description={DRAFT_EMPTY_STATE.description}
                />
              )}
              {inactiveAgents.length > 0 ? (
                <AgentStatusSection label="사용 안함" className="min-h-70.75">
                  <div className="flex w-full flex-col gap-3">
                    {inactiveAgents.map((agent) => (
                      <AgentCard
                        key={agent.id}
                        agent={agent}
                        layout="grouped"
                        onActivate={(target) => updateStatus(target.id, 'active')}
                      />
                    ))}
                  </div>
                </AgentStatusSection>
              ) : (
                <AgentEmptyColumn
                  label="사용 안함"
                  title={INACTIVE_EMPTY_STATE.title}
                  description={INACTIVE_EMPTY_STATE.description}
                />
              )}
            </>
          ) : (
            <>
              {shouldShowActiveEmpty && (
                <AgentEmptyColumn
                  label="운영중"
                  title={ACTIVE_EMPTY_STATE.title}
                  description={ACTIVE_EMPTY_STATE.description}
                  layout="flat"
                />
              )}
              {activeAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  layout="flat"
                  onDeactivate={(target) => updateStatus(target.id, 'inactive')}
                />
              ))}
              {draftAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  layout="flat"
                  onDeactivate={(target) => updateStatus(target.id, 'inactive')}
                />
              ))}
              {shouldShowDraftEmpty && (
                <AgentEmptyColumn
                  label="제작중"
                  title={DRAFT_EMPTY_STATE.title}
                  description={DRAFT_EMPTY_STATE.description}
                  layout="flat"
                />
              )}
              {inactiveAgents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  layout="flat"
                  onActivate={(target) => updateStatus(target.id, 'active')}
                />
              ))}
              {shouldShowInactiveEmpty && (
                <AgentEmptyColumn
                  label="사용 안함"
                  title={INACTIVE_EMPTY_STATE.title}
                  description={INACTIVE_EMPTY_STATE.description}
                  layout="flat"
                />
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}

function AgentStudioListPreview() {
  return (
    <div style={{ minHeight: 720 }}>
      <AgentStudioListFixturePreview />
    </div>
  );
}

function AgentStudioEditorPreview() {
  return (
    <div style={{ minHeight: 720 }}>
      <AgentStudioEditorPage />
    </div>
  );
}

export const agentStudioListFigmaCase: FigmaLabCase = {
  id: 'agent-studio-list-page',
  groupId: 'agent-studio',
  owner: 'feature',
  component: 'AgentStudioPage',
  state: 'fixture-default',
  kind: 'page',
  title: 'Agent Studio / List Page',
  description: '좌측 SNB를 제외한 Agent Studio 목록 화면을 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14795-99034&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14795:99034',
  },
  targetRoute: '/agent-studio',
  viewport: {
    width: 1184,
    height: 720,
  },
  layout: {
    shell: 'App shell content without SNB',
    container: 'Header -> team agent section',
    stack: 'Page header -> title -> filter row -> agent cards',
    responsive: ['desktop source frame for this pass'],
    relationships: [
      {
        from: 'Header',
        to: 'Team agent section',
        figma: '24px vertical offset',
        code: 'pt-6',
      },
      {
        from: 'Filter tabs',
        to: 'Create agent button',
        figma: '20px horizontal gap',
        code: 'gap-5',
      },
      {
        from: 'Agent cards',
        to: 'Empty columns',
        figma: '24px horizontal gap',
        code: 'gap-6',
      },
    ],
  },
  data: {
    source: 'fixture',
    fixtures: ['AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE', 'AGENT_STUDIO_FILTERS', 'AGENT_STUDIO_LIST_FIXTURE'],
    states: [
      {
        state: 'fixtureDefault',
        fixture: 'AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE',
        expected: '운영중 Agent 카드 3개가 같은 행에 표시됩니다.',
      },
      {
        state: 'activeEmptyAfterDeactivate',
        fixture: 'AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE',
        expected: '운영중 카드에서 사용 안함을 눌러 active가 비면, 운영중 빈 컬럼이 유지됩니다.',
      },
      {
        state: 'filterTabs',
        fixture: 'AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE',
        expected: '운영중, 제작중, 사용 안함 탭을 클릭하면 해당 상태의 카드 또는 빈 컬럼만 표시됩니다.',
      },
    ],
    notes: [
      '사용 안함 Agent 카드 본문은 node 14844:104963 기준으로 다시 운영하기 CTA를 표시합니다.',
      '운영중 빈 컬럼은 node 14844:104803 구조를 기준으로 상태 색상과 문구를 맞춥니다.',
    ],
  },
  states: ['fixtureDefault', 'activeEmptyAfterDeactivate', 'filterTabs'],
  reuse: [
    {
      figmaPart: 'Create agent button',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '공통 Button variant를 사용하고 아이콘만 asset으로 연결합니다.',
    },
    {
      figmaPart: 'Filter tabs',
      checked: 'src/shared/components/ui/chips.tsx',
      decision: 'reuse',
      reason: '상태 필터는 공통 Chip 컴포넌트로 선택/기본 상태를 표현합니다.',
    },
    {
      figmaPart: 'Agent cards',
      checked: 'src/features/agent-studio/components/list',
      decision: 'feature-local',
      reason: '목록 fixture와 상태별 카드 표시는 Agent Studio feature-local 조립입니다.',
    },
    {
      figmaPart: 'Inactive agent card CTA',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '사용 안함 카드의 다시 운영하기 CTA는 공통 capsule outline Button을 전체 폭으로 사용합니다.',
    },
  ],
  tokens: [
    {
      figma: 'header horizontal padding',
      value: '16px',
      code: 'px-16',
      decision: 'scale-mapped',
    },
    {
      figma: 'section top padding',
      value: '24px',
      code: 'pt-6',
      decision: 'scale-mapped',
    },
    {
      figma: 'card row gap',
      value: '24px',
      code: 'gap-6',
      decision: 'scale-mapped',
    },
    {
      figma: 'use button icon and text',
      value: 'static/white',
      code: 'text-static-white',
      decision: 'matched',
    },
    {
      figma: 'use button radial gradient',
      value: 'radial-gradient(circle at 50% 3%, ...)',
      code: 'bg-agent-studio-use-button-gradient',
      decision: 'project-token',
    },
    {
      figma: 'inactive card restart button',
      value: '36px full width outline capsule',
      code: 'capsule-outline-mono h-9 w-full',
      decision: 'matched',
    },
  ],
  render: () => <AgentStudioListPreview />,
};

export const agentStudioEditorFigmaCase: FigmaLabCase = {
  id: 'agent-studio-editor-page',
  groupId: 'agent-studio',
  owner: 'feature',
  component: 'AgentStudioEditorPage',
  state: 'fixture-default',
  kind: 'page',
  title: 'Agent Studio / Editor Page',
  description: 'Agent 만들기 진입 후 좌측 설명 영역과 우측 설정 영역을 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14775-126519&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14775:126519',
  },
  targetRoute: '/agent-studio/new',
  viewport: {
    width: 1280,
    height: 720,
  },
  layout: {
    shell: 'Closed SNB route content',
    container: 'Left description pane plus right settings pane',
    stack: 'Left pane header/content, right pane header/settings',
    responsive: ['desktop source frame for this pass'],
    relationships: [
      {
        from: 'Left pane',
        to: 'Right settings pane',
        figma: '420px fixed left pane followed by flexible settings pane',
        code: 'w-105 and flex-1',
      },
      {
        from: 'Right header',
        to: 'Settings body',
        figma: '20px top padding',
        code: 'pt-5',
      },
      {
        from: 'Settings sections',
        to: 'Settings sections',
        figma: '32px vertical gap',
        code: 'gap-8',
      },
    ],
  },
  data: {
    source: 'fixture',
    fixtures: ['AGENT_STUDIO_SETTINGS_FIXTURE'],
    states: [
      {
        state: 'fixtureDefault',
        fixture: 'AGENT_STUDIO_SETTINGS_FIXTURE',
        expected: '채널톡 유입 감지와 Slack 메시지 전송 설정이 기본 fixture 값으로 표시됩니다.',
      },
    ],
  },
  states: ['fixtureDefault'],
  reuse: [
    {
      figmaPart: 'Input/select field',
      checked: 'src/shared/components/ui/select.tsx',
      decision: 'reuse',
      reason: '선택형 설정 필드는 공통 Select 컴포넌트를 사용합니다.',
    },
    {
      figmaPart: 'Deploy button',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '우측 헤더의 배포 버튼은 공통 Button의 disabled 상태를 사용합니다.',
    },
    {
      figmaPart: 'Workflow setting cards',
      checked: 'src/features/agent-studio/components/editor',
      decision: 'feature-local',
      reason: '워크플로우 단계별 설명과 설정 조합은 Agent Studio feature-local 영역입니다.',
    },
  ],
  tokens: [
    {
      figma: 'left pane width',
      value: '420px',
      code: 'w-105',
      decision: 'scale-mapped',
    },
    {
      figma: 'right settings body horizontal padding',
      value: '36px',
      code: 'px-9',
      decision: 'scale-mapped',
    },
    {
      figma: 'settings vertical gap',
      value: '32px',
      code: 'gap-8',
      decision: 'scale-mapped',
    },
    {
      figma: 'select placeholder text',
      value: 'text/nomal/assistive',
      code: 'data-placeholder:text-text-normal-assistive',
      decision: 'matched',
    },
  ],
  render: () => <AgentStudioEditorPreview />,
};
