import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import DocumentSearchFilterRow from './DocumentSearchFilterRow';
import SmartFilterStatusPill from './SmartFilterStatusPill';

describe('DocumentSearchFilterRow', () => {
  it('renders manual filter chips and Smart Filter switch', () => {
    render(
      <DocumentSearchFilterRow
        selectedSources={[]}
        onSourcesChange={vi.fn()}
        dateRange={undefined}
        onDateRangeChange={vi.fn()}
        smartFilter={true}
        onSmartFilterChange={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '검색 범위 필터' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '날짜 필터' })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: '스마트 필터' })).toBeChecked();
  });

  it('calls onSmartFilterChange when switch is toggled', async () => {
    const user = userEvent.setup();
    const onSmartFilterChange = vi.fn();
    render(
      <DocumentSearchFilterRow
        selectedSources={[]}
        onSourcesChange={vi.fn()}
        dateRange={undefined}
        onDateRangeChange={vi.fn()}
        smartFilter={true}
        onSmartFilterChange={onSmartFilterChange}
      />,
    );

    await user.click(screen.getByRole('switch', { name: '스마트 필터' }));
    expect(onSmartFilterChange).toHaveBeenCalledWith(false);
  });

  it('SmartFilterStatusPill renders applied indicator when enabled', () => {
    render(<SmartFilterStatusPill enabled />);
    expect(screen.getByText('스마트 필터 적용됨')).toBeInTheDocument();
  });

  it('SmartFilterStatusPill renders CTA and calls handler when disabled', async () => {
    const user = userEvent.setup();
    const onApplyClick = vi.fn();
    render(<SmartFilterStatusPill enabled={false} onApplyClick={onApplyClick} />);

    await user.click(screen.getByRole('button', { name: '스마트 필터 적용하기' }));
    expect(onApplyClick).toHaveBeenCalledTimes(1);
  });
});
