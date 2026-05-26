import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ResultSearchBar from './ResultSearchBar';

vi.mock('./ResultSearchBarExpandedPanel', () => ({
  default: () => <div data-testid="expanded-panel" />,
}));

function makeDefaultProps() {
  return {
    value: '',
    onValueChange: vi.fn(),
    chips: [],
    onChipsChange: vi.fn(),
    dateRange: undefined,
    onDateRangeChange: vi.fn(),
    onSubmit: vi.fn(),
    onHistorySubmit: vi.fn(),
    onClear: vi.fn(),
    onAiModeClick: vi.fn(),
  };
}

describe('ResultSearchBar', () => {
  it('검색어가 비어 있어도 AI 모드 버튼을 렌더링한다', () => {
    render(<ResultSearchBar {...makeDefaultProps()} />);

    expect(screen.getByRole('button', { name: 'AI 모드' })).toBeInTheDocument();
  });

  it('expanded 상태에서도 AI 모드 버튼을 유지하고 클릭 핸들러를 호출한다', async () => {
    const user = userEvent.setup();
    const onAiModeClick = vi.fn();

    render(<ResultSearchBar {...makeDefaultProps()} value="검색어 text" onAiModeClick={onAiModeClick} />);

    await user.click(screen.getByRole('textbox'));
    expect(screen.getByTestId('expanded-panel')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'AI 모드' }));
    expect(onAiModeClick).toHaveBeenCalledTimes(1);
  });
});
