import type { ReactNode } from 'react';

export interface FigmaReference {
  url: string;
  fileKey: string;
  nodeId: string;
}

export interface FigmaLabViewport {
  width: number;
  height?: number;
}

export type FigmaLabCaseKind = 'component' | 'section' | 'page';
export type FigmaLabGroupId =
  | 'hybrid-search'
  | 'home-docs'
  | 'agent-studio'
  | 'shared-query-filter'
  | 'shared-status'
  | 'original-panel';
export type FigmaLabCaseOwner = 'feature' | 'shared';
export type FigmaLabDesignSource = 'figma' | 'dev-preview';

export interface FigmaLabGroup {
  id: FigmaLabGroupId;
  title: string;
  description: string;
  defaultCaseId?: string;
  relatedGroupIds?: readonly FigmaLabGroupId[];
}

export interface FigmaLabLayoutRelationship {
  from: string;
  to: string;
  figma: string;
  code: string;
  note?: string;
}

export interface FigmaLabLayoutContract {
  shell?: string;
  container?: string;
  stack?: string;
  responsive?: readonly string[];
  relationships: readonly FigmaLabLayoutRelationship[];
}

export type FigmaLabDataSource = 'fixture' | 'mock' | 'api-contract' | 'static';

export interface FigmaLabStateContract {
  state: string;
  fixture: string;
  expected: string;
  note?: string;
}

export interface FigmaLabDataContract {
  source: FigmaLabDataSource;
  api?: string;
  fixtures: readonly string[];
  states: readonly FigmaLabStateContract[];
  notes?: readonly string[];
}

export interface FigmaLabReuseDecision {
  figmaPart: string;
  checked: string;
  decision: 'reuse' | 'extend' | 'feature-local' | 'new-shared' | 'rejected';
  reason: string;
}

export interface FigmaLabTokenDecision {
  figma: string;
  value?: string;
  code: string;
  decision: 'matched' | 'scale-mapped' | 'project-token' | 'drift-recorded' | 'unmapped';
}

export interface FigmaLabCase {
  id: string;
  groupId: FigmaLabGroupId;
  owner: FigmaLabCaseOwner;
  designSource?: FigmaLabDesignSource;
  component: string;
  state: string;
  usedBy?: readonly FigmaLabGroupId[];
  kind: FigmaLabCaseKind;
  title: string;
  description?: string;
  figma?: FigmaReference;
  targetRoute?: string;
  viewport: FigmaLabViewport;
  layout?: FigmaLabLayoutContract;
  data?: FigmaLabDataContract;
  states: readonly string[];
  reuse: readonly FigmaLabReuseDecision[];
  tokens: readonly FigmaLabTokenDecision[];
  notes?: readonly string[];
  render: () => ReactNode;
}
