import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { TooltipProvider } from '@/shared/components/ui/tooltip';

import NavTree, { type NavTreeNode } from './NavTree';

const CHANNEL = '채널 1';
const FOLDER = '폴더 1';
const FILE = '파일 1';

const TREE: readonly NavTreeNode[] = [
  {
    id: 'channel-1',
    label: CHANNEL,
    Icon: IconWikiChannel,
    children: [
      { id: 'folder-1', label: FOLDER, Icon: IconFolder, children: [{ id: 'file-1', label: FILE, Icon: IconFile }] },
    ],
  },
];

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

function renderTree() {
  return render(
    <TooltipProvider>
      <NavTree nodes={TREE} defaultExpandedIds={['channel-1', 'folder-1']} onNodeClick={vi.fn()} />
    </TooltipProvider>,
  );
}

/** 캐럿은 hover·포커스에서만 나타난다 — jsdom엔 Tailwind가 없어 포커스만 주면 잡힌다 */
async function collapse(user: ReturnType<typeof userEvent.setup>, label: string) {
  screen.getByRole('button', { name: label }).focus();
  await user.click(screen.getByRole('button', { name: `${label} 접기` }));
}

afterEach(() => {
  window.matchMedia = realMatchMedia;
});

describe('NavTree 접기·펼치기', () => {
  it('하위 목록이 overflow-hidden 상자 안에 들어가 접히는 동안 밖으로 새지 않는다', () => {
    setReducedMotion(false);
    const { container } = renderTree();

    const list = screen.getByRole('button', { name: FOLDER }).closest('ul')!;
    expect(list.parentElement!.parentElement).toHaveClass('overflow-hidden');

    // 행과 하위 목록 사이 간격은 상자 안쪽이 든다 — 접힌 뒤 빈 gap이 남지 않게
    const item = container.querySelector('li')!;
    expect(item.className).not.toMatch(/gap-/);
  });

  it('접으면 하위 목록이 애니메이션을 마친 뒤에 사라진다', async () => {
    setReducedMotion(false);
    const user = userEvent.setup();
    renderTree();

    expect(screen.getByRole('button', { name: FILE })).toBeInTheDocument();

    await collapse(user, CHANNEL);
    // 나가는 중에는 아직 트리에 있다 — 즉시 사라지면 높이가 한 번에 튄다
    expect(screen.queryByRole('button', { name: FOLDER })).toBeInTheDocument();

    await waitFor(() => expect(screen.queryByRole('button', { name: FOLDER })).toBeNull());
    expect(screen.queryByRole('button', { name: FILE })).toBeNull();
  });

  it('reduced motion이면 접힘이 다음 프레임에 끝난다', async () => {
    setReducedMotion(true);
    const user = userEvent.setup();
    renderTree();

    await collapse(user, CHANNEL);

    // disclosureExpandReduced는 duration 0이다. exit 0.15s를 쓰는 원본이면 이 예산을 넘긴다
    await waitFor(() => expect(screen.queryByRole('button', { name: FOLDER })).toBeNull(), {
      timeout: 120,
      interval: 5,
    });
  });
});
