import { HOME_DOCS_FIGMA_LAB_CASES } from './features/home-docs';
import { HYBRID_SEARCH_FIGMA_LAB_CASES } from './features/hybrid-search';
import { SHARED_QUERY_FILTER_FIGMA_LAB_CASES } from './features/shared-query-filter';
import { FIGMA_LAB_GROUPS, findFigmaLabGroup, isFigmaLabGroupId } from './groups';
import type { FigmaLabCase, FigmaLabGroupId } from './types';

interface FigmaLabRouteCaseOptions {
  selectedCaseId?: string;
  groupId?: FigmaLabGroupId;
}

export const FIGMA_LAB_CASES: readonly FigmaLabCase[] = [
  ...HYBRID_SEARCH_FIGMA_LAB_CASES,
  ...HOME_DOCS_FIGMA_LAB_CASES,
  ...SHARED_QUERY_FILTER_FIGMA_LAB_CASES,
];

export function findFigmaLabCase(id: string | undefined): FigmaLabCase | undefined {
  if (!id) return undefined;

  return FIGMA_LAB_CASES.find((item) => item.id === id);
}

export function getDefaultFigmaLabCaseId(groupId?: FigmaLabGroupId): string | undefined {
  if (groupId) {
    const group = findFigmaLabGroup(groupId);
    if (group?.defaultCaseId) return group.defaultCaseId;

    return getVisibleFigmaLabCasesByGroup(groupId)[0]?.id;
  }

  return FIGMA_LAB_CASES[0]?.id;
}

export function getFigmaLabCasesByGroup(groupId: FigmaLabGroupId): readonly FigmaLabCase[] {
  return FIGMA_LAB_CASES.filter((item) => item.groupId === groupId);
}

export function getRelatedFigmaLabCasesByGroup(groupId: FigmaLabGroupId): readonly FigmaLabCase[] {
  const group = findFigmaLabGroup(groupId);
  const relatedGroupIds = new Set(group?.relatedGroupIds ?? []);

  return FIGMA_LAB_CASES.filter((item) => {
    if (!relatedGroupIds.has(item.groupId)) return false;

    return item.usedBy?.includes(groupId) ?? false;
  });
}

export function getVisibleFigmaLabCasesByGroup(groupId: FigmaLabGroupId): readonly FigmaLabCase[] {
  return [...getFigmaLabCasesByGroup(groupId), ...getRelatedFigmaLabCasesByGroup(groupId)];
}

export function getFigmaLabCaseForRoute({
  selectedCaseId,
  groupId,
}: FigmaLabRouteCaseOptions): FigmaLabCase | undefined {
  if (!groupId) {
    return findFigmaLabCase(selectedCaseId ?? getDefaultFigmaLabCaseId());
  }

  const visibleCases = getVisibleFigmaLabCasesByGroup(groupId);
  const selectedCase = selectedCaseId ? visibleCases.find((item) => item.id === selectedCaseId) : undefined;
  if (selectedCase) return selectedCase;

  const defaultCaseId = getDefaultFigmaLabCaseId(groupId);
  return visibleCases.find((item) => item.id === defaultCaseId);
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
    if (!isFigmaLabGroupId(item.groupId)) {
      errors.push(`Case '${item.id}' must include a valid groupId.`);
    }
    if (item.owner !== 'feature' && item.owner !== 'shared') {
      errors.push(`Case '${item.id}' must include a valid owner.`);
    }
    if (!item.component) {
      errors.push(`Case '${item.id}' must include component.`);
    }
    if (!item.state) {
      errors.push(`Case '${item.id}' must include state.`);
    }
    for (const usedByGroupId of item.usedBy ?? []) {
      if (!FIGMA_LAB_GROUPS.some((group) => group.id === usedByGroupId)) {
        errors.push(`Case '${item.id}' usedBy group '${usedByGroupId}' is not registered.`);
      }
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
    if (item.data) {
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
