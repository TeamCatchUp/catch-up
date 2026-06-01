import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ResultPageBody from './ResultPageBody';

describe('ResultPageBody', () => {
  it('matches the result body shell layout', () => {
    const { container } = render(
      <ResultPageBody side={<div data-testid="original-panel">Original panel</div>}>
        <div data-testid="result-list">Result list</div>
      </ResultPageBody>,
    );

    const section = container.querySelector('section');
    expect(section).toHaveClass('min-h-0', 'flex-1', 'overflow-hidden', 'px-16');
    expect(section).not.toHaveClass('pb-30');

    const shell = section?.firstElementChild;
    expect(shell).toHaveClass('h-full', 'min-h-0', 'max-w-355', 'items-stretch', 'gap-6', 'overflow-hidden');

    const leftColumn = screen.getByTestId('result-list').parentElement;
    expect(leftColumn).toHaveClass(
      'custom-scrollbar',
      'min-h-0',
      'min-w-156.25',
      'flex-1',
      'flex-col',
      'items-center',
      'gap-10',
      'overflow-x-clip',
      'overflow-y-auto',
      'pt-4',
      'pr-2',
      'pb-30',
    );
    expect(leftColumn).not.toHaveClass('w-156.25', 'shrink-0');

    const rightPanel = screen.getByTestId('original-panel').parentElement;
    expect(rightPanel).toHaveClass(
      'custom-scrollbar',
      'flex',
      'min-h-0',
      'min-w-105',
      'w-105.75',
      'shrink-0',
      'flex-col',
      'overflow-y-auto',
      'overscroll-contain',
      'border-l',
    );
    expect(rightPanel).not.toHaveClass('max-h-340');
  });
});
