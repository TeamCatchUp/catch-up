import type { FigmaLabCase, FigmaLabDataContract, FigmaLabLayoutContract } from './types';

export const validCase: FigmaLabCase = {
  id: 'admin-users-table',
  groupId: 'hybrid-search',
  owner: 'feature',
  component: 'UsersTable',
  state: 'default',
  kind: 'component',
  title: 'Admin/UsersTable',
  figma: {
    url: 'https://figma.com/design/file/Design?node-id=1-2',
    fileKey: 'file',
    nodeId: '1:2',
  },
  targetRoute: '/admin/integrations',
  viewport: {
    width: 1020,
    height: 720,
  },
  states: ['default'],
  reuse: [
    {
      figmaPart: 'Button',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: 'Existing Button covers this state.',
    },
  ],
  tokens: [
    {
      figma: 'Text/Normal',
      code: 'text-content-normal',
      decision: 'matched',
    },
  ],
  render: () => 'Admin users table case',
};

export const validPageLayout: FigmaLabLayoutContract = {
  shell: 'Admin app shell',
  container: 'max-w content area with page padding',
  stack: 'Page header -> users status section -> users table',
  responsive: ['desktop frame is the source of truth for this pass'],
  relationships: [
    {
      from: 'Page header',
      to: 'Users table',
      figma: '24px vertical gap',
      code: 'gap-6',
    },
  ],
};

export const validPageData: FigmaLabDataContract = {
  source: 'fixture',
  fixtures: ['adminIntegrationsPageFixture.default', 'adminIntegrationsPageFixture.empty'],
  states: [
    {
      state: 'default',
      fixture: 'adminIntegrationsPageFixture.default',
      expected: 'Header, status section, and users table are visible.',
    },
    {
      state: 'empty',
      fixture: 'adminIntegrationsPageFixture.empty',
      expected: 'Empty table state preserves page spacing.',
    },
  ],
};

export const validPageCase: FigmaLabCase = {
  ...validCase,
  id: 'admin-integrations-page',
  kind: 'page',
  title: 'Admin/Integrations/Page',
  states: ['default', 'empty'],
  layout: validPageLayout,
  data: validPageData,
};

export const validDevPreviewCase: FigmaLabCase = {
  id: 'channel-talk-text-content',
  groupId: 'hybrid-search',
  owner: 'feature',
  designSource: 'dev-preview',
  component: 'TextContent',
  state: 'fixture-preview',
  kind: 'component',
  title: 'ChannelTalk/TextContent',
  viewport: {
    width: 420,
    height: 240,
  },
  states: ['fixture-preview'],
  reuse: [
    {
      figmaPart: 'dev preview',
      checked: 'src/features/hybrid-search/components/original/channel-talk/contents/TextContent.tsx',
      decision: 'feature-local',
      reason: 'This fixture preview renders the production feature component without a dedicated Figma node.',
    },
  ],
  tokens: [],
  notes: ['Dev-preview case intentionally has no Figma node or token contract.'],
  render: () => 'ChannelTalk text preview',
};
