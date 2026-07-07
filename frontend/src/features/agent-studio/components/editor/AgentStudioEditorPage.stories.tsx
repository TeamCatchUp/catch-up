'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import AgentStudioEditorPage from './AgentStudioEditorPage';

const agentStudioEditorHandlers = [
  http.get(API.automations.credentials, ({ request }) => {
    const connector = new URL(request.url).searchParams.get('connector');

    if (connector !== 'slack') {
      return HttpResponse.json({
        connector,
        total_credentials: 0,
        credentials: [],
      });
    }

    return HttpResponse.json({
      connector: 'slack',
      total_credentials: 1,
      credentials: [
        {
          connector: 'slack',
          credential_id: 501,
          display_name: 'CatchUp Slack',
          external_id: 'T_CATCHUP',
          external_name: 'CatchUp Workspace',
          is_configured: true,
          metadata: {},
        },
      ],
    });
  }),
  http.get(API.automations.targets, ({ request }) => {
    const searchParams = new URL(request.url).searchParams;
    const connector = searchParams.get('connector');

    if (connector === 'channel_talk') {
      return HttpResponse.json({
        connector: 'channel_talk',
        credential_id: null,
        total_targets: 1,
        targets: [
          {
            connector: 'channel_talk',
            credential_id: 301,
            target_id: 'channel-talk-support',
            display_name: 'CatchUp 고객 문의',
            target_type: 'channel',
            is_accessible: true,
            metadata: {},
          },
        ],
      });
    }

    if (connector === 'slack') {
      return HttpResponse.json({
        connector: 'slack',
        credential_id: 501,
        total_targets: 1,
        targets: [
          {
            connector: 'slack',
            credential_id: 501,
            target_id: 'C_HELPDESK',
            display_name: '#support-agent',
            target_type: 'channel',
            is_accessible: true,
            metadata: {},
          },
        ],
      });
    }

    return HttpResponse.json({
      connector,
      credential_id: null,
      total_targets: 0,
      targets: [],
    });
  }),
  http.post(API.automations.publishInquiry, () =>
    HttpResponse.json({
      agent_spec_id: 9001,
      trigger_id: 8001,
      status: 'active',
      channel_talk_channel_id: 'channel-talk-support',
      channel_talk_channel_name: 'CatchUp 고객 문의',
      quiet_period_seconds: 180,
      slack_channel_id: 'C_HELPDESK',
      start_event_type: 'message.created',
      reset_event_types: ['message.updated'],
    }),
  ),
];

const meta = {
  title: 'Screens/Agent Studio/Editor',
  component: AgentStudioEditorPage,
  tags: ['autodocs'],
  parameters: {
    msw: {
      handlers: agentStudioEditorHandlers,
    },
    ...catchupParameters({
      level: 'screen',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      figmaLab: {
        caseId: 'agent-studio-editor-page',
        groupId: 'agent-studio',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14775-126519&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14775:126519',
      },
      viewport: {
        width: 1280,
        height: 720,
      },
      states: ['fixture-default'],
      dataNotes: [
        'Story-level MSW handlers provide Slack credentials, Slack targets, ChannelTalk targets, and publish response.',
      ],
      reuseNotes: [
        'Screen composes AgentEditorLeftPane and AgentEditorSettings.',
        'Settings controls reuse shared Button, Select, DropdownMenu, and Tooltip components.',
      ],
    }),
  },
} satisfies Meta<typeof AgentStudioEditorPage>;

export default meta;

type Story = StoryObj<typeof meta>;

export const CreateDefault: Story = {
  render: () => (
    <div style={{ minHeight: 720 }}>
      <AgentStudioEditorPage />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { name: '설정' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '배포하기' })).toBeInTheDocument();
  },
};
