import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ResultSearchBar from './ResultSearchBar';

vi.mock('./ResultSearchBarExpandedPanel', () => ({
  default: ({
    smartFilter,
    onFilterOverlayOpenChange,
  }: {
    smartFilter: boolean;
    onFilterOverlayOpenChange: (open: boolean) => void;
  }) => (
    <div data-testid="expanded-panel">
      expanded smart: {String(smartFilter)}
      <button
        type="button"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => onFilterOverlayOpenChange(true)}
      >
        필터 팝오버 열기
      </button>
    </div>
  ),
}));

function makeDefaultProps() {
  return {
    value: '',
    onValueChange: vi.fn(),
    chips: [],
    onChipsChange: vi.fn(),
    dateRange: undefined,
    onDateRangeChange: vi.fn(),
    smartFilter: true,
    draftSmartFilter: true,
    onDraftSmartFilterChange: vi.fn(),
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

  it('Enter 키 입력 시 submit handler를 호출한다', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<ResultSearchBar {...makeDefaultProps()} value="회의록" onSubmit={onSubmit} />);

    await user.click(screen.getByRole('textbox'));
    await user.keyboard('{Enter}');

    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('collapsed Smart Filter ON이면 적용됨 표시를 렌더링한다', () => {
    render(<ResultSearchBar {...makeDefaultProps()} smartFilter />);
    expect(screen.getByText('스마트 필터 적용됨')).toBeInTheDocument();
  });

  it('collapsed Smart Filter OFF이면 적용 CTA를 렌더링한다', () => {
    render(<ResultSearchBar {...makeDefaultProps()} smartFilter={false} />);
    expect(screen.getByText('기본 검색 결과')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '스마트 필터 적용하기' })).toBeInTheDocument();
  });

  it('collapsed CTA 클릭 시 draft Smart Filter를 켜고 expanded panel을 연다', async () => {
    const user = userEvent.setup();
    const onDraftSmartFilterChange = vi.fn();

    render(
      <ResultSearchBar
        {...makeDefaultProps()}
        smartFilter={false}
        draftSmartFilter={false}
        onDraftSmartFilterChange={onDraftSmartFilterChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: '스마트 필터 적용하기' }));

    expect(screen.getByTestId('expanded-panel')).toBeInTheDocument();
    expect(onDraftSmartFilterChange).toHaveBeenCalledWith(true);
  });

  it('expanded 상태에서도 URL 기준 Smart Filter 상태 pill을 유지한다', async () => {
    const user = userEvent.setup();

    render(<ResultSearchBar {...makeDefaultProps()} value="회의록" smartFilter />);

    await user.click(screen.getByRole('textbox'));

    expect(screen.getByTestId('expanded-panel')).toBeInTheDocument();
    expect(screen.getByText('스마트 필터 적용됨')).toBeInTheDocument();
  });

  it('expanded panel은 draft Smart Filter를 쓰고 상단 pill은 URL 기준 상태를 유지한다', async () => {
    const user = userEvent.setup();

    render(<ResultSearchBar {...makeDefaultProps()} value="회의록" smartFilter={false} draftSmartFilter />);

    await user.click(screen.getByRole('textbox'));

    expect(screen.getByTestId('expanded-panel')).toHaveTextContent('expanded smart: true');
    expect(screen.getByText('기본 검색 결과')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '스마트 필터 적용하기' })).toBeInTheDocument();
  });

  it('expanded 내부 필터 팝오버가 열릴 때 검색 input blur로 panel이 닫히지 않는다', async () => {
    const user = userEvent.setup();

    render(<ResultSearchBar {...makeDefaultProps()} value="회의록" />);

    const input = screen.getByRole('textbox');
    await user.click(input);
    expect(screen.getByTestId('expanded-panel')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '필터 팝오버 열기' }));
    fireEvent.blur(input);

    await waitFor(() => {
      expect(screen.getByTestId('expanded-panel')).toBeInTheDocument();
    });
  });

  it('top row에서 기간 필터 버튼을 렌더링하지 않는다', () => {
    render(<ResultSearchBar {...makeDefaultProps()} />);
    expect(screen.queryByRole('button', { name: '기간 필터' })).not.toBeInTheDocument();
  });
});
