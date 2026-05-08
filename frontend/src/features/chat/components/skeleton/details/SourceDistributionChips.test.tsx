import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SourceDistributionChips from './SourceDistributionChips';

describe('SourceDistributionChips', () => {
  it('distribution이 비어 있으면 그리지 않는다', () => {
    const { container } = render(<SourceDistributionChips distribution={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('각 platform별로 라벨 + count chip을 그린다', () => {
    render(
      <SourceDistributionChips
        distribution={{ jira: 11, github: 11, slack: 11, confluence: 11 }}
      />,
    );
    expect(screen.getByText('Confluence')).toBeInTheDocument();
    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('Jira')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getAllByText('11')).toHaveLength(4);
  });

  it('count가 0이거나 음수인 항목은 제외한다', () => {
    render(<SourceDistributionChips distribution={{ jira: 0, github: 5 }} />);
    expect(screen.queryByText('Jira')).not.toBeInTheDocument();
    expect(screen.getByText('GitHub')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('지정된 정렬 순서(confluence/github/jira/slack)를 따른다', () => {
    const { container } = render(
      <SourceDistributionChips
        distribution={{ slack: 1, jira: 2, confluence: 3, github: 4 }}
      />,
    );
    const text = container.textContent ?? '';
    const order = ['Confluence', 'GitHub', 'Jira', 'Slack'].map((p) => text.indexOf(p));
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });
});
