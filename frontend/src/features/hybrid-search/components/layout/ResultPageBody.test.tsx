import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ResultPageBody from './ResultPageBody';

describe('ResultPageBody', () => {
  it('matches the Figma result body shell layout', () => {
    const { container } = render(
      <ResultPageBody side={<div data-testid="original-panel">Original panel</div>}>
        <div data-testid="result-list">Result list</div>
      </ResultPageBody>,
    );

    const section = container.querySelector('section');
    expect(section).toHaveClass('px-16', 'pb-30');

    const shell = section?.firstElementChild;
    expect(shell).toHaveClass('max-w-[1420px]', 'items-start', 'gap-6');

    const leftColumn = screen.getByTestId('result-list').parentElement;
    expect(leftColumn).toHaveClass(
      'min-w-156.25',
      'flex-1',
      'flex-col',
      'items-center',
      'gap-10',
      'overflow-x-clip',
      'overflow-y-auto',
      'py-4',
    );
    expect(leftColumn).not.toHaveClass('w-156.25', 'shrink-0');

    const rightPanel = screen.getByTestId('original-panel').parentElement;
    expect(rightPanel).toHaveClass(
      'custom-scrollbar',
      'w-105.75',
      'shrink-0',
      'overflow-y-auto',
      'overscroll-contain',
      'border-l',
    );
  });
});
