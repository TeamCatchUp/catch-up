interface CatchupStoryParametersBase {
  level: 'primitive' | 'composition' | 'screen';
  domain: 'shared' | 'home' | 'hybrid-search' | 'chat' | 'agent-studio' | 'admin' | 'onboarding' | 'llm-wiki';
  fsdLayer: 'shared' | 'entities' | 'features' | 'widgets' | 'app';
  owner: 'shared' | 'feature' | 'widget' | 'app';
  dataProfile: 'static' | 'realistic-fixture' | 'msw' | 'empty' | 'loading' | 'error';
  figmaLab?: {
    caseId: string;
    groupId: 'hybrid-search' | 'agent-studio' | 'shared-query-filter' | 'shared-status' | 'original-panel';
  };
  viewport?: {
    width: number;
    height?: number;
  };
  states: readonly string[];
  usedBy?: readonly ('home-docs' | 'hybrid-search' | 'chat' | 'agent-studio')[];
  layoutNotes?: readonly string[];
  dataNotes?: readonly string[];
  reuseNotes?: readonly string[];
  interactionNotes?: readonly string[];
  tokenNotes?: readonly string[];
}

interface FigmaStoryParameters extends CatchupStoryParametersBase {
  designSource: 'figma';
  figma: {
    url: string;
    fileKey: string;
    nodeId: string;
  };
}

interface DevPreviewStoryParameters extends CatchupStoryParametersBase {
  designSource?: 'dev-preview';
  figma?: never;
}

export type CatchupStoryParameters = FigmaStoryParameters | DevPreviewStoryParameters;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function requireNonEmptyString(value: unknown, field: string): asserts value is string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`catchupParameters.${field} must be a non-empty string.`);
  }
}

export function validateCatchupStoryParameters(parameters: unknown): asserts parameters is CatchupStoryParameters {
  if (!isRecord(parameters)) {
    throw new Error('catchupParameters must receive an object.');
  }

  if (!Array.isArray(parameters.states) || parameters.states.length === 0) {
    throw new Error('catchupParameters.states must include at least one state.');
  }

  if (parameters.viewport !== undefined) {
    if (
      !isRecord(parameters.viewport) ||
      typeof parameters.viewport.width !== 'number' ||
      parameters.viewport.width <= 0
    ) {
      throw new Error('catchupParameters.viewport.width must be greater than 0.');
    }
    if (
      parameters.viewport.height !== undefined &&
      (typeof parameters.viewport.height !== 'number' || parameters.viewport.height <= 0)
    ) {
      throw new Error('catchupParameters.viewport.height must be greater than 0.');
    }
  }

  const designSource = parameters.designSource ?? 'dev-preview';
  if (designSource !== 'figma' && designSource !== 'dev-preview') {
    throw new Error("catchupParameters.designSource must be 'figma' or 'dev-preview'.");
  }

  if (designSource === 'figma') {
    if (!isRecord(parameters.figma)) {
      throw new Error("catchupParameters.figma is required when designSource is 'figma'.");
    }

    requireNonEmptyString(parameters.figma.url, 'figma.url');
    requireNonEmptyString(parameters.figma.fileKey, 'figma.fileKey');
    requireNonEmptyString(parameters.figma.nodeId, 'figma.nodeId');

    const figmaUrl = new URL(parameters.figma.url);
    if (figmaUrl.protocol !== 'https:' || !figmaUrl.hostname.endsWith('figma.com')) {
      throw new Error('catchupParameters.figma.url must be an HTTPS Figma URL.');
    }

    const urlNodeId = figmaUrl.searchParams.get('node-id')?.replaceAll('-', ':');
    if (urlNodeId && urlNodeId !== parameters.figma.nodeId) {
      throw new Error('catchupParameters.figma.nodeId must match the Figma URL node-id.');
    }
  } else if (parameters.figma !== undefined) {
    throw new Error("catchupParameters.figma requires designSource: 'figma'.");
  }
}

export function catchupParameters(parameters: CatchupStoryParameters) {
  validateCatchupStoryParameters(parameters);

  return {
    catchup: parameters,
  };
}
