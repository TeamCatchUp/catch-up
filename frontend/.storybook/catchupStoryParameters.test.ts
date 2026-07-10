import { describe, expect, it } from 'vitest';

import { validateCatchupStoryParameters } from './catchupStoryParameters';

const baseParameters = {
  level: 'composition',
  domain: 'agent-studio',
  fsdLayer: 'features',
  owner: 'feature',
  dataProfile: 'realistic-fixture',
  states: ['default'],
};

describe('catchupStoryParameters', () => {
  it('accepts dev previews without Figma metadata', () => {
    expect(() =>
      validateCatchupStoryParameters({
        ...baseParameters,
        designSource: 'dev-preview',
      }),
    ).not.toThrow();
  });

  it('requires Figma metadata for Figma-backed stories', () => {
    expect(() =>
      validateCatchupStoryParameters({
        ...baseParameters,
        designSource: 'figma',
      }),
    ).toThrow("catchupParameters.figma is required when designSource is 'figma'.");
  });

  it('accepts complete and consistent Figma metadata', () => {
    expect(() =>
      validateCatchupStoryParameters({
        ...baseParameters,
        designSource: 'figma',
        figma: {
          url: 'https://www.figma.com/design/file-key/CatchUp?node-id=12-34&m=dev',
          fileKey: 'file-key',
          nodeId: '12:34',
        },
      }),
    ).not.toThrow();
  });

  it('rejects mismatched Figma node identifiers', () => {
    expect(() =>
      validateCatchupStoryParameters({
        ...baseParameters,
        designSource: 'figma',
        figma: {
          url: 'https://www.figma.com/design/file-key/CatchUp?node-id=12-34&m=dev',
          fileKey: 'file-key',
          nodeId: '56:78',
        },
      }),
    ).toThrow('catchupParameters.figma.nodeId must match the Figma URL node-id.');
  });

  it('rejects empty states and invalid viewport dimensions', () => {
    expect(() => validateCatchupStoryParameters({ ...baseParameters, states: [] })).toThrow(
      'catchupParameters.states must include at least one state.',
    );
    expect(() => validateCatchupStoryParameters({ ...baseParameters, viewport: { width: 0 } })).toThrow(
      'catchupParameters.viewport.width must be greater than 0.',
    );
  });
});
