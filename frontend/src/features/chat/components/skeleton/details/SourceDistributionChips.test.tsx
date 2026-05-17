import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SourceDistributionChips from './SourceDistributionChips';

describe('SourceDistributionChips', () => {
  it('distribution이 비어 있으면 그리지 않는다', () => {
    const { container } = render(<SourceDistributionChips distribution={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('각 platform별로 아이콘 + count chip을 그린다', () => {
    const { container } = render(
      <SourceDistributionChips distribution={{ jira: 11, github: 11, slack: 11, confluence: 11 }} />,
    );
    expect(screen.getAllByText('11')).toHaveLength(4);
    expect(container.querySelectorAll('svg')).toHaveLength(4);
  });

  it('count가 0이거나 음수인 항목은 제외한다', () => {
    const { container } = render(<SourceDistributionChips distribution={{ jira: 0, github: 5 }} />);
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.queryByText('0')).not.toBeInTheDocument();
    expect(container.querySelectorAll('svg')).toHaveLength(1);
  });

  it('지정된 정렬 순서(confluence/github/jira/slack)를 따른다', () => {
    const { container } = render(
      <SourceDistributionChips distribution={{ slack: 1, jira: 2, confluence: 3, github: 4 }} />,
    );
    // 렌더 순서: confluence(3) → github(4) → jira(2) → slack(1)
    const text = container.textContent ?? '';
    const order = ['3', '4', '2', '1'].map((c) => text.indexOf(c));
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });
});
