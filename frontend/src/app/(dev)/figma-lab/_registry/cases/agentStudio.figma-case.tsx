import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';
import AgentStudioEditorPage from '@/features/agent-studio/components/editor/AgentStudioEditorPage';
import AgentStudioPage from '@/features/agent-studio/components/list/AgentStudioPage';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';

function AgentStudioListPreview() {
  return (
    <div style={{ minHeight: 720 }}>
      <AgentStudioPage />
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
    fixtures: ['AGENT_STUDIO_LIST_FIXTURE', 'AGENT_STUDIO_FILTERS'],
    states: [
      {
        state: 'fixtureDefault',
        fixture: 'AGENT_STUDIO_LIST_FIXTURE',
        expected: '운영 중 Agent 카드 1개와 제작중/사용 안함 빈 컬럼이 같은 행에 표시됩니다.',
      },
    ],
  },
  states: ['fixtureDefault'],
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
  ],
  render: () => <AgentStudioEditorPreview />,
};
