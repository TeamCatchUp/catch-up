import type { ReactNode } from 'react';

import type { FigmaLabCase, FigmaReference } from '../../types';
import { DESIGN_SYSTEM_FILE_KEY } from '../caseConstants';
import {
  ORIGINAL_PANEL_ENTRIES,
  type OriginalPanelCaseId,
  type OriginalPanelEntry,
} from './originalPanelEntries';
import { channelTalkMetadataRenderers } from './renderers/channelTalkMetadataRenderers';
import { channelTalkRenderers } from './renderers/channelTalkRenderers';
import { panelStateRenderers } from './renderers/panelStateRenderers';
import { slackRenderers } from './renderers/slackRenderers';

const ORIGINAL_PANEL_RENDERERS = {
  ...channelTalkRenderers,
  ...channelTalkMetadataRenderers,
  ...panelStateRenderers,
  ...slackRenderers,
} satisfies Partial<Record<OriginalPanelCaseId, () => ReactNode>>;

const SLACK_FIGMA_REFERENCES: Partial<Record<OriginalPanelCaseId, FigmaReference>> = {
  'slack-thread-header': {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14152-56904&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14152:56904',
  },
  'slack-message-item': {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14427-58787&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14427:58787',
  },
  'slack-rich-message': {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14444-60860&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14444:60860',
  },
  'slack-panel-preview': {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14152-56488&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14152:56488',
  },
};

function originalPanelViewport(caseId: OriginalPanelCaseId): FigmaLabCase['viewport'] {
  if (caseId === 'slack-panel-preview' || caseId === 'panel-content' || caseId === 'panel') {
    return { width: 520, height: 760 };
  }
  if (caseId.startsWith('slack-')) {
    return { width: 480, height: 420 };
  }
  return { width: 460, height: 420 };
}

function checkedPath(caseId: OriginalPanelCaseId): string {
  if (caseId.startsWith('slack-')) {
    return 'src/features/hybrid-search/components/original/slack';
  }
  if (caseId.startsWith('panel-') || caseId === 'panel' || caseId === 'date-indicator') {
    return 'src/features/hybrid-search/components/original/shared';
  }
  return 'src/features/hybrid-search/components/original/channel-talk';
}

function originalPanelCaseKind(caseId: OriginalPanelCaseId): FigmaLabCase['kind'] {
  if (caseId === 'slack-panel-preview' || caseId === 'panel-content' || caseId === 'panel') {
    return 'section';
  }
  return 'component';
}

function createOriginalPanelCase(entry: OriginalPanelEntry): FigmaLabCase {
  const render = ORIGINAL_PANEL_RENDERERS[entry.id];
  if (!render) {
    throw new Error(`Missing original-panel renderer for '${entry.id}'.`);
  }

  const figma = SLACK_FIGMA_REFERENCES[entry.id];
  const isFigmaBacked = Boolean(figma);

  return {
    id: entry.id,
    groupId: 'original-panel',
    owner: 'feature',
    designSource: isFigmaBacked ? 'figma' : 'dev-preview',
    component: entry.title,
    state: isFigmaBacked ? 'figma-fixture-preview' : 'fixture-preview',
    kind: originalPanelCaseKind(entry.id),
    title: entry.title,
    description: entry.description,
    figma,
    viewport: originalPanelViewport(entry.id),
    states: [isFigmaBacked ? 'figma-fixture-preview' : 'fixture-preview'],
    reuse: [
      {
        figmaPart: entry.title,
        checked: checkedPath(entry.id),
        decision: 'feature-local',
        reason: isFigmaBacked
          ? 'Slack original panel case renders the production feature component against the linked Figma node.'
          : 'Dev-preview case renders the production feature component with fixture data and no dedicated Figma node.',
      },
    ],
    tokens: isFigmaBacked
      ? [
          {
            figma: 'Original panel semantic styles',
            code: 'Tailwind semantic tokens in production original panel components',
            decision: 'project-token',
          },
        ]
      : [],
    notes: [
      isFigmaBacked
        ? 'Figma-backed Slack case uses fixture data to isolate layout and rendering states.'
        : 'Dev-preview case intentionally has no Figma node; it preserves the old original-panel gallery coverage.',
    ],
    render,
  };
}

export const ORIGINAL_PANEL_FIGMA_LAB_CASES = ORIGINAL_PANEL_ENTRIES.map(
  createOriginalPanelCase,
) satisfies readonly FigmaLabCase[];
