import { describe, expect, it } from 'vitest';

import { FIGMA_LAB_CASES, findFigmaLabCase, getDefaultFigmaLabCaseId, validateFigmaLabCases } from './cases';
import type { FigmaLabCase, FigmaLabDataContract, FigmaLabLayoutContract } from './types';

const validCase: FigmaLabCase = {
  id: 'admin-users-table',
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

const validPageLayout: FigmaLabLayoutContract = {
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

const validPageData: FigmaLabDataContract = {
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

const validPageCase: FigmaLabCase = {
  ...validCase,
  id: 'admin-integrations-page',
  kind: 'page',
  title: 'Admin/Integrations/Page',
  states: ['default', 'empty'],
  layout: validPageLayout,
  data: validPageData,
};

describe('figma lab registry', () => {
  it('starts with no registered cases', () => {
    expect(FIGMA_LAB_CASES).toEqual([]);
  });

  it('returns undefined when a case id is unknown', () => {
    expect(findFigmaLabCase('missing-case')).toBeUndefined();
  });

  it('returns undefined when there is no default case', () => {
    expect(getDefaultFigmaLabCaseId()).toBeUndefined();
  });

  it('accepts an empty registry while the harness has no pilot case', () => {
    expect(validateFigmaLabCases([])).toEqual([]);
  });

  it('accepts complete story-like cases', () => {
    expect(validateFigmaLabCases([validCase])).toEqual([]);
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
