import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import UnderlineTabs, { type UnderlineTabItem } from './underline-tabs';

type TabValue = 'one' | 'two' | 'three';

const ITEMS: readonly UnderlineTabItem<TabValue>[] = [
  { value: 'one', label: '하나' },
  { value: 'two', label: '둘' },
  { value: 'three', label: '셋' },
];

function Harness({
  initial = 'one',
  onValueChange,
}: {
  initial?: TabValue;
  onValueChange?: (v: TabValue) => void;
}) {
  const [value, setValue] = useState<TabValue>(initial);
  return (
    <UnderlineTabs<TabValue>
      items={ITEMS}
      value={value}
      onValueChange={(v) => {
        setValue(v);
        onValueChange?.(v);
      }}
      ariaLabel="테스트 탭"
    />
  );
}

describe('UnderlineTabs', () => {
  it('모든 label을 렌더하고 활성 항목에 data-state="active" 가 부여된다', () => {
    render(<Harness initial="two" />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(3);
    expect(tabs.map((t) => t.textContent)).toEqual(['하나', '둘', '셋']);
    expect(tabs[1]).toHaveAttribute('data-state', 'active');
    expect(tabs[0]).toHaveAttribute('data-state', 'inactive');
  });

  it('비활성 탭 클릭 시 onValueChange가 해당 value로 호출된다', async () => {
    const user = userEvent.setup();
    const handle = vi.fn<(v: TabValue) => void>();
    render(<Harness initial="one" onValueChange={handle} />);

    await user.click(screen.getByRole('tab', { name: '셋' }));

    expect(handle).toHaveBeenCalledWith('three');
  });

  it('ArrowRight 키로 다음 탭으로 이동한다', async () => {
    const user = userEvent.setup();
    const handle = vi.fn<(v: TabValue) => void>();
    render(<Harness initial="one" onValueChange={handle} />);

    await user.click(screen.getByRole('tab', { name: '하나' }));
    handle.mockClear();
    await user.keyboard('{ArrowRight}');

    expect(handle).toHaveBeenCalledWith('two');
  });
});
