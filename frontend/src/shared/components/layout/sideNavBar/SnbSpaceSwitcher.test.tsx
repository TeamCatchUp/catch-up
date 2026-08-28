import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { SPACE_HOME_ICON, SPACE_WIKI_ICON } from './snbNavFixtures';
import SnbSpaceSwitcher, { SPACE_SWITCHER_LAYOUT_ID } from './SnbSpaceSwitcher';

const realMatchMedia = window.matchMedia;

/** usePrefersReducedMotion이 보는 자리를 갈아끼운다. 훅이 effect에서 읽으므로 렌더 전에 세운다 */
function setReducedMotion(reduce: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: reduce && query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

/** 실제 소비처(SideNavShell)와 같은 한 줄 배치의 최소 조립 */
function SwitcherPair() {
  const [space, setSpace] = useState<'home' | 'wiki'>('home');
  return (
    <div className="flex items-center gap-1.5">
      <SnbSpaceSwitcher
        Icon={SPACE_HOME_ICON}
        label="홈"
        selected={space === 'home'}
        onClick={() => setSpace('home')}
      />
      <SnbSpaceSwitcher
        Icon={SPACE_WIKI_ICON}
        label="LLM Wiki"
        selected={space === 'wiki'}
        onClick={() => setSpace('wiki')}
      />
    </div>
  );
}

/** 홈·위키 SNB처럼 트리째 갈리는 배치. 같은 layoutId로만 폭 전환이 이어진다 */
function SwappedNav({ space }: { space: 'home' | 'wiki' }) {
  return (
    <div className="flex items-center gap-1.5">
      {space === 'home' ? (
        <>
          <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" layoutId={SPACE_SWITCHER_LAYOUT_ID.home} selected />
          <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" layoutId={SPACE_SWITCHER_LAYOUT_ID.wiki} />
        </>
      ) : (
        <>
          <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" layoutId={SPACE_SWITCHER_LAYOUT_ID.home} />
          <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" layoutId={SPACE_SWITCHER_LAYOUT_ID.wiki} selected />
        </>
      )}
    </div>
  );
}

afterEach(() => {
  window.matchMedia = realMatchMedia;
});

describe('SnbSpaceSwitcher 선택 전환', () => {
  it('선택이 옮겨가면 라벨과 aria-current가 함께 옮겨간다', async () => {
    setReducedMotion(false);
    const user = userEvent.setup();
    render(<SwitcherPair />);

    expect(screen.getByText('홈')).toBeInTheDocument();
    expect(screen.queryByText('LLM Wiki')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'LLM Wiki' }));

    expect(screen.getByText('LLM Wiki')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'LLM Wiki' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '홈' })).not.toHaveAttribute('aria-current');
    // 나가는 라벨은 페이드가 끝난 뒤 사라진다
    await waitFor(() => expect(screen.queryByText('홈')).toBeNull());
  });

  it('SNB가 통째로 갈려도 선택 표시가 새 트리로 넘어간다', async () => {
    setReducedMotion(false);
    const { rerender } = render(<SwappedNav space="home" />);

    expect(screen.getByRole('button', { name: '홈' })).toHaveAttribute('aria-current', 'page');

    // 라우팅으로 SNB 컴포넌트가 교체되는 상황
    rerender(<SwappedNav space="wiki" />);

    expect(screen.getByRole('button', { name: 'LLM Wiki' })).toHaveAttribute('aria-current', 'page');
    await waitFor(() => expect(screen.queryByText('홈')).toBeNull());
  });

  it('두 SNB가 같은 layoutId를 써야 폭 전환이 이어진다', () => {
    // 값이 갈리면 교체 순간 두 버튼이 각자 새로 그려져 전환이 끊긴다
    expect(SPACE_SWITCHER_LAYOUT_ID.home).not.toBe(SPACE_SWITCHER_LAYOUT_ID.wiki);
    expect(Object.values(SPACE_SWITCHER_LAYOUT_ID).every(Boolean)).toBe(true);
  });

  it('reduced motion이면 나가는 라벨이 짧은 예산 안에 사라진다', async () => {
    setReducedMotion(true);
    const user = userEvent.setup();
    render(<SwitcherPair />);

    await user.click(screen.getByRole('button', { name: 'LLM Wiki' }));

    // layoutLabelFadeReduced의 exit는 0.08s다. 0.3s를 쓰는 원본이면 이 예산도 결정적으로 넘긴다
    await waitFor(() => expect(screen.queryByText('홈')).toBeNull(), { timeout: 250, interval: 5 });
  });
});
