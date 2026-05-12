import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import AccentTabs, { type AccentTabItem } from './accent-tabs';

type TabValue = 'info' | 'files' | 'comments';

function Harness({
  items,
  initial = 'info',
  onValueChange,
}: {
  items: readonly AccentTabItem<TabValue>[];
  initial?: TabValue;
  onValueChange?: (v: TabValue) => void;
}) {
  const [value, setValue] = useState<TabValue>(initial);
  return (
    <AccentTabs<TabValue>
      items={items}
      value={value}
      onValueChange={(v) => {
        setValue(v);
        onValueChange?.(v);
      }}
      ariaLabel="테스트 탭"
    />
  );
}

const PLAIN_ITEMS: readonly AccentTabItem<TabValue>[] = [
  { value: 'info', label: 'Info' },
  { value: 'files', label: '첨부파일' },
  { value: 'comments', label: '댓글' },
];

describe('AccentTabs', () => {
  it('모든 label을 렌더하고 활성 항목에 data-state="active" 가 부여된다', () => {
    render(<Harness items={PLAIN_ITEMS} initial="files" />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(3);
    expect(tabs[1]).toHaveAttribute('data-state', 'active');
    expect(tabs[0]).toHaveAttribute('data-state', 'inactive');
  });

  it('비활성 탭 클릭 시 onValueChange가 해당 value로 호출된다', async () => {
    const user = userEvent.setup();
    const handle = vi.fn<(v: TabValue) => void>();
    render(<Harness items={PLAIN_ITEMS} initial="info" onValueChange={handle} />);

    await user.click(screen.getByRole('tab', { name: '댓글' }));

    expect(handle).toHaveBeenCalledWith('comments');
  });

  it('ArrowRight 키로 다음 탭으로 이동한다', async () => {
    const user = userEvent.setup();
    const handle = vi.fn<(v: TabValue) => void>();
    render(<Harness items={PLAIN_ITEMS} initial="info" onValueChange={handle} />);

    await user.click(screen.getByRole('tab', { name: 'Info' }));
    handle.mockClear();
    await user.keyboard('{ArrowRight}');

    expect(handle).toHaveBeenCalledWith('files');
  });

  describe('카운트 배지', () => {
    it('count가 양수면 해당 숫자가 표시된다', () => {
      const items: readonly AccentTabItem<TabValue>[] = [
        { value: 'info', label: 'Info' },
        { value: 'files', label: '첨부파일', count: 3 },
        { value: 'comments', label: '댓글' },
      ];
      render(<Harness items={items} />);
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('count가 0이면 0이 표시된다', () => {
      const items: readonly AccentTabItem<TabValue>[] = [
        { value: 'info', label: 'Info' },
        { value: 'files', label: '첨부파일', count: 0 },
      ];
      render(<Harness items={items} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('count가 undefined면 배지가 렌더되지 않는다', () => {
      const items: readonly AccentTabItem<TabValue>[] = [
        { value: 'info', label: 'Info' },
        { value: 'files', label: '첨부파일' },
      ];
      const { container } = render(<Harness items={items} />);
      expect(container.querySelector('[data-tab-state-badge]')).toBeNull();
    });
  });
});
