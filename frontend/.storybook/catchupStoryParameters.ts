export interface CatchupStoryParameters {
  level: 'primitive' | 'composition' | 'screen';
  domain: 'shared' | 'home' | 'hybrid-search' | 'chat' | 'agent-studio' | 'admin' | 'onboarding';
  fsdLayer: 'shared' | 'entities' | 'features' | 'widgets' | 'app';
  owner: 'shared' | 'feature' | 'widget' | 'app';
  dataProfile: 'static' | 'realistic-fixture' | 'msw' | 'empty' | 'loading' | 'error';
  figmaLab?: {
    caseId: string;
    groupId: 'hybrid-search' | 'agent-studio' | 'shared-query-filter' | 'shared-status' | 'original-panel';
  };
  designSource?: 'figma' | 'dev-preview';
  figma?: {
    url: string;
    fileKey: string;
    nodeId: string;
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

export function catchupParameters(parameters: CatchupStoryParameters) {
  return {
    catchup: parameters,
  };
}
