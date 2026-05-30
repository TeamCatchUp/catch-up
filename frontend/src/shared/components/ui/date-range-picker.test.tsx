import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DateRangePicker } from './date-range-picker';

const selectedRange = {
  from: new Date(2026, 4, 1),
  to: new Date(2026, 4, 2),
};

describe('DateRangePicker', () => {
  it('keeps the current value when closing without reset or apply', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DateRangePicker value={selectedRange} onChange={onChange} />);

    await user.click(screen.getByText('2026.05.01'));
    await user.click(await screen.findByRole('button', { name: '닫기' }));

    expect(onChange).not.toHaveBeenCalled();
  });

  it('commits an explicit reset when closing without apply', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DateRangePicker value={selectedRange} onChange={onChange} />);

    await user.click(screen.getByText('2026.05.01'));
    await user.click(await screen.findByRole('button', { name: '초기화' }));
    await user.click(screen.getByRole('button', { name: '닫기' }));

    expect(onChange).toHaveBeenCalledWith(undefined);
  });
});
