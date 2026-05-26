import type { FigmaLabCase } from './types';

export const FIGMA_LAB_CASES: readonly FigmaLabCase[] = [];

export function findFigmaLabCase(id: string | undefined): FigmaLabCase | undefined {
  if (!id) return undefined;

  return FIGMA_LAB_CASES.find((item) => item.id === id);
}

export function getDefaultFigmaLabCaseId(): string | undefined {
  return FIGMA_LAB_CASES[0]?.id;
}

export function validateFigmaLabCases(cases: readonly FigmaLabCase[]): string[] {
  const errors: string[] = [];
  const ids = new Set<string>();

  for (const item of cases) {
    if (ids.has(item.id)) {
      errors.push(`Duplicate figma lab case id: '${item.id}'.`);
    }
    ids.add(item.id);

    if (!item.figma?.url) {
      errors.push(`Case '${item.id}' must include figma.url.`);
    }
    if (!item.figma?.fileKey) {
      errors.push(`Case '${item.id}' must include figma.fileKey.`);
    }
    if (!item.figma?.nodeId) {
      errors.push(`Case '${item.id}' must include figma.nodeId.`);
    }
    if (item.viewport.width <= 0) {
      errors.push(`Case '${item.id}' viewport.width must be greater than 0.`);
    }
    if (!item.kind) {
      errors.push(`Case '${item.id}' must include kind.`);
    }
    if (item.kind === 'page' && !item.targetRoute) {
      errors.push(`Case '${item.id}' with kind 'page' must include targetRoute.`);
    }
    if (item.kind === 'page' && !item.layout) {
      errors.push(`Case '${item.id}' with kind 'page' must include layout metadata.`);
    }
    if (item.kind === 'page' && item.layout && item.layout.relationships.length === 0) {
      errors.push(`Case '${item.id}' with kind 'page' must include at least one layout relationship.`);
    }
    if (item.kind === 'page' && !item.data) {
      errors.push(`Case '${item.id}' with kind 'page' must include data/state metadata.`);
    }
    if (item.kind === 'page' && item.data && item.data.fixtures.length === 0) {
      errors.push(`Case '${item.id}' with kind 'page' must include at least one data fixture.`);
    }
    if (item.kind === 'page' && item.data && item.data.states.length === 0) {
      errors.push(`Case '${item.id}' with kind 'page' must include at least one data state contract.`);
    }
    if (item.kind === 'page' && item.data) {
      const coveredStates = new Set(item.data.states.map((stateContract) => stateContract.state));
      for (const state of item.states) {
        if (!coveredStates.has(state)) {
          errors.push(`Case '${item.id}' state '${state}' must be covered by data.states.`);
        }
      }
    }
    if (item.states.length === 0) {
      errors.push(`Case '${item.id}' must include at least one state.`);
    }
    if (item.reuse.length === 0) {
      errors.push(`Case '${item.id}' must include at least one reuse decision.`);
    }
    if (item.tokens.length === 0) {
      errors.push(`Case '${item.id}' must include at least one token decision.`);
    }
  }

  return errors;
}
