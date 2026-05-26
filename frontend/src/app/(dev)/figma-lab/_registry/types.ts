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
  kind: FigmaLabCaseKind;
  title: string;
  description?: string;
  figma?: FigmaReference;
  targetRoute?: string;
  viewport: FigmaLabViewport;
  layout?: FigmaLabLayoutContract;
  states: readonly string[];
  reuse: readonly FigmaLabReuseDecision[];
  tokens: readonly FigmaLabTokenDecision[];
  notes?: readonly string[];
  render: () => ReactNode;
}
