import { describe, expect, it } from 'vitest';

import {
  FIGMA_LAB_CASES,
  findFigmaLabCase,
  getDefaultFigmaLabCaseId,
  getFigmaLabCaseForRoute,
  getFigmaLabCasesByGroup,
  getRelatedFigmaLabCasesByGroup,
  getVisibleFigmaLabCasesByGroup,
  validateFigmaLabCases,
} from './cases';
import {
  validCase,
  validDevPreviewCase,
  validPageCase,
  validPageData,
  validPageLayout,
} from './cases.test.fixtures';
import type { FigmaLabCase } from './types';

describe('figma lab registry', () => {
  it('registers the smart filter UI cases without metadata errors', () => {
    expect(FIGMA_LAB_CASES.map((item) => item.id)).toEqual([
      'result-search-bar-collapsed',
      'result-search-bar-expanded',
      'document-search-filter-row-entry',
      'document-search-filter-row-source-dropdown-open',
      'document-search-filter-row-date-picker-open',
      'document-search-filter-row-result-expanded',
      'smart-filter-status-pill',
    ]);
    expect(validateFigmaLabCases(FIGMA_LAB_CASES)).toEqual([]);
  });

  it('returns undefined when a case id is unknown', () => {
    expect(findFigmaLabCase('missing-case')).toBeUndefined();
  });

  it('returns the first registered case as the default case', () => {
    expect(getDefaultFigmaLabCaseId()).toBe('result-search-bar-collapsed');
  });

  it('returns the group default case when a group is selected', () => {
    expect(getDefaultFigmaLabCaseId('hybrid-search')).toBe('result-search-bar-expanded');
    expect(getDefaultFigmaLabCaseId('shared-query-filter')).toBe('document-search-filter-row-entry');
  });

  it('returns feature cases and related shared cases by group', () => {
    expect(getFigmaLabCasesByGroup('hybrid-search').map((item) => item.id)).toEqual([
      'result-search-bar-collapsed',
      'result-search-bar-expanded',
    ]);
    expect(getRelatedFigmaLabCasesByGroup('hybrid-search').map((item) => item.id)).toEqual([
      'document-search-filter-row-entry',
      'document-search-filter-row-source-dropdown-open',
      'document-search-filter-row-date-picker-open',
      'document-search-filter-row-result-expanded',
      'smart-filter-status-pill',
    ]);
    expect(getVisibleFigmaLabCasesByGroup('home-docs').map((item) => item.id)).toEqual([
      'document-search-filter-row-entry',
      'document-search-filter-row-source-dropdown-open',
      'document-search-filter-row-date-picker-open',
    ]);
  });

  it('keeps group routes scoped to visible cases', () => {
    expect(
      getFigmaLabCaseForRoute({
        groupId: 'home-docs',
        selectedCaseId: 'result-search-bar-expanded',
      })?.id,
    ).toBe('document-search-filter-row-entry');
    expect(
      getFigmaLabCaseForRoute({
        groupId: 'home-docs',
        selectedCaseId: 'document-search-filter-row-source-dropdown-open',
      })?.id,
    ).toBe('document-search-filter-row-source-dropdown-open');
  });

  it('accepts an empty registry while the harness has no pilot case', () => {
    expect(validateFigmaLabCases([])).toEqual([]);
  });

  it('accepts complete story-like cases', () => {
    expect(validateFigmaLabCases([validCase])).toEqual([]);
  });

  it('accepts dev-preview cases without Figma metadata or token decisions', () => {
    expect(validateFigmaLabCases([validDevPreviewCase])).toEqual([]);
  });

  it('rejects dev-preview cases without notes', () => {
    const errors = validateFigmaLabCases([
      {
        ...validDevPreviewCase,
        notes: [],
      },
    ]);

    expect(errors).toContain("Case 'channel-talk-text-content' dev-preview must include at least one note.");
  });

  it('accepts page cases with route and layout metadata', () => {
    expect(validateFigmaLabCases([validPageCase])).toEqual([]);
  });

  it('rejects page cases without target routes', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        targetRoute: undefined,
      },
    ]);

    expect(errors).toContain("Case 'admin-integrations-page' with kind 'page' must include targetRoute.");
  });

  it('rejects page cases without layout metadata', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        layout: undefined,
      },
    ]);

    expect(errors).toContain("Case 'admin-integrations-page' with kind 'page' must include layout metadata.");
  });

  it('rejects page cases without layout relationships', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        layout: {
          ...validPageLayout,
          relationships: [],
        },
      },
    ]);

    expect(errors).toContain(
      "Case 'admin-integrations-page' with kind 'page' must include at least one layout relationship.",
    );
  });

  it('rejects page cases without data/state metadata', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        data: undefined,
      },
    ]);

    expect(errors).toContain("Case 'admin-integrations-page' with kind 'page' must include data/state metadata.");
  });

  it('rejects page cases without data fixtures', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        data: {
          ...validPageData,
          fixtures: [],
        },
      },
    ]);

    expect(errors).toContain("Case 'admin-integrations-page' with kind 'page' must include at least one data fixture.");
  });

  it('rejects page cases without state contracts', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        data: {
          ...validPageData,
          states: [],
        },
      },
    ]);

    expect(errors).toContain(
      "Case 'admin-integrations-page' with kind 'page' must include at least one data state contract.",
    );
  });

  it('rejects page cases when declared visual states are not covered by data contracts', () => {
    const errors = validateFigmaLabCases([
      {
        ...validPageCase,
        data: {
          ...validPageData,
          states: validPageData.states.slice(0, 1),
        },
      },
    ]);

    expect(errors).toContain("Case 'admin-integrations-page' state 'empty' must be covered by data.states.");
  });

  it('rejects component cases when declared visual states are not covered by data contracts', () => {
    const errors = validateFigmaLabCases([
      {
        ...validCase,
        data: {
          ...validPageData,
          states: [
            {
              ...validPageData.states[0],
              state: 'selected',
            },
          ],
        },
      },
    ]);

    expect(errors).toContain("Case 'admin-users-table' state 'default' must be covered by data.states.");
  });

  it('rejects duplicate case ids', () => {
    const errors = validateFigmaLabCases([
      validCase,
      {
        ...validCase,
        title: 'Duplicate Admin/UsersTable',
      },
    ]);

    expect(errors).toContain("Duplicate figma lab case id: 'admin-users-table'.");
  });

  it('rejects registered cases without a case kind', () => {
    const caseWithoutKind = { ...validCase };
    delete (caseWithoutKind as { kind?: unknown }).kind;

    const errors = validateFigmaLabCases([caseWithoutKind]);

    expect(errors).toContain("Case 'admin-users-table' must include kind.");
  });

  it('rejects registered cases without ownership metadata', () => {
    const errors = validateFigmaLabCases([
      {
        ...validCase,
        groupId: 'missing-group',
        owner: 'unknown',
        component: '',
        state: '',
        usedBy: ['missing-related-group'],
      } as unknown as FigmaLabCase,
    ]);

    expect(errors).toContain("Case 'admin-users-table' must include a valid groupId.");
    expect(errors).toContain("Case 'admin-users-table' must include a valid owner.");
    expect(errors).toContain("Case 'admin-users-table' must include component.");
    expect(errors).toContain("Case 'admin-users-table' must include state.");
    expect(errors).toContain("Case 'admin-users-table' usedBy group 'missing-related-group' is not registered.");
  });

  it('rejects registered cases without Figma metadata', () => {
    const errors = validateFigmaLabCases([
      {
        ...validCase,
        figma: undefined,
      },
    ]);

    expect(errors).toContain("Case 'admin-users-table' must include figma.url.");
    expect(errors).toContain("Case 'admin-users-table' must include figma.fileKey.");
    expect(errors).toContain("Case 'admin-users-table' must include figma.nodeId.");
  });

  it('rejects registered cases without reuse or token decisions', () => {
    const errors = validateFigmaLabCases([
      {
        ...validCase,
        reuse: [],
        tokens: [],
      },
    ]);

    expect(errors).toContain("Case 'admin-users-table' must include at least one reuse decision.");
    expect(errors).toContain("Case 'admin-users-table' must include at least one token decision.");
  });

  it('rejects invalid viewport and missing state coverage', () => {
    const errors = validateFigmaLabCases([
      {
        ...validCase,
        viewport: { width: 0 },
        states: [],
      },
    ]);

    expect(errors).toContain("Case 'admin-users-table' viewport.width must be greater than 0.");
    expect(errors).toContain("Case 'admin-users-table' must include at least one state.");
  });
});
