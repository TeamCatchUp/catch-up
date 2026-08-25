import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import NavTree from '@/shared/components/navigation/NavTree';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SideNavShell from './SideNavShell';
import SnbChatTitleRow from './SnbChatTitleRow';
import SnbFooter from './SnbFooter';
import {
  HOME_AGENT_ITEMS,
  HOME_FAVORITE_ITEMS,
  HOME_PRIMARY_ITEMS,
  HOME_RECENT_TITLES,
  PROJECT_TREE_NODES,
  SPACE_HOME_ICON,
  SPACE_WIKI_ICON,
  TEAMSPACE_ICON,
  WIKI_DROPDOWN_ITEMS,
  WIKI_PRIMARY_ITEMS,
} from './snbNavFixtures';
import SnbNavRow from './SnbNavRow';
import SnbSectionHeader, { SnbBetaBadge } from './SnbSectionHeader';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';
import SnbTeamspaceCard from './SnbTeamspaceCard';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Shell/SideNavShell',
  component: SideNavShell,
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17859-129062',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17859:129062',
      },
      viewport: { width: 280, height: 1024 },
      states: ['home-expanded', 'wiki-expanded', 'empty-sections'],
      layoutNotes: [
        '섹션 구성은 소비처가 조립한다 — 홈과 위키가 다르고 그 구성 자체가 미결이다.',
        'Figma 실측으로는 위키만 스크롤 페이드를 가진다. 홈에도 켠 것은 최근 질문 목록 복원에 따른 잠정이다(design-request #15).',
      ],
      dataNotes: [
        '로딩·빈 목록·에러 스토리를 만들지 않는다 — 시안에 없다(docs/state-audit/전역-snb.md §7).',
        '트리 라벨은 시안 placeholder 그대로다.',
      ],
      reuseNotes: ['NavTree는 slot으로 주입만 한다 — 이 배치는 NavTree를 수정하지 않는다.'],
    }),
  },
} satisfies Meta<typeof SideNavShell>;

export default meta;

type Story = StoryObj<typeof SideNavShell>;

const noop = () => {};

export const HomeExpanded: Story = {
  args: { onCollapse: fn(), showScrollFade: true },
  render: (args) => (
    <SideNavShell
      {...args}
      spaceSwitcher={
        <>
          <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" selected onClick={noop} />
          <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" onClick={noop} />
        </>
      }
      primaryItems={
        <div className="flex flex-col">
          {HOME_PRIMARY_ITEMS.map((item) => (
            <SnbNavRow key={item.id} {...item} trailing={item.beta ? <SnbBetaBadge /> : undefined} onClick={noop} />
          ))}
        </div>
      }
      footer={<SnbFooter userName="팀원G" userRole="PM" />}
    >
      <div className="flex flex-col gap-1">
        <SnbSectionHeader label="에이전트" badge={<SnbBetaBadge />} />
        {HOME_AGENT_ITEMS.map((item) => (
          <SnbNavRow key={item.id} {...item} onClick={noop} />
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader label="즐겨찾기" />
        {HOME_FAVORITE_ITEMS.map((item) => (
          <SnbNavRow key={item.id} {...item} onClick={noop} />
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader label="최근 질문" />
        {HOME_RECENT_TITLES.map((title, index) => (
          <SnbChatTitleRow key={index} label={title} onClick={noop} onMoreClick={noop} />
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader label="프로젝트" />
        <NavTree
          nodes={PROJECT_TREE_NODES}
          defaultExpandedIds={['channel-1', 'folder-1']}
          onNodeClick={noop}
          onNodeMore={noop}
          onNodeAdd={noop}
        />
      </div>
    </SideNavShell>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('에이전트')).toBeInTheDocument();
    await expect(canvas.getByText('최근 질문')).toBeInTheDocument();
    await expect(canvas.getByText('프로젝트')).toBeInTheDocument();
    // 트리는 slot으로 들어온다
    await expect(canvas.getByRole('button', { name: '파일명texttexttexttext' })).toBeInTheDocument();
    // 건수 배지는 대응 집계가 없어 걷어냈다 — 되살아나면 근거 없는 숫자가 다시 보인다
    await expect(canvas.queryByTestId('snb-nav-row-count')).toBeNull();

    await step('셸 골격 치수를 값으로 고정한다', async () => {
      const nav = canvasElement.querySelector('nav')!;
      const navArea = canvas.getByTestId('side-nav-shell-nav-area');
      const box = (el: Element) => el.getBoundingClientRect();

      await expect(Math.round(box(nav).width)).toBe(240);
      await expect(Math.round(box(nav.children[0].children[0]).height)).toBe(56);
      await expect(getComputedStyle(navArea).rowGap).toBe('20px');
      await expect(getComputedStyle(navArea).paddingLeft).toBe('8px');
      // 모드 스위처 아래 주 내비 블록은 12 간격이다
      await expect(getComputedStyle(navArea.children[0]).rowGap).toBe('12px');
      await expect(Math.round(box(nav.children[1]).height)).toBe(97);
    });

    await step('트리 들여쓰기는 행이 아니라 행 안에서 일어난다', async () => {
      const rows = [...canvasElement.querySelectorAll('[data-slot="nav-tree-row"]')];
      const left = (el: Element) => el.getBoundingClientRect().left;
      const iconLeft = (row: Element) => left(row.querySelector('span:has(> svg)')!);

      // 배경은 전 depth가 같은 자리다 — 셸 안에서도 폭이 줄지 않는다
      await expect(left(rows[1])).toBe(left(rows[0]));
      await expect(left(rows[2])).toBe(left(rows[0]));
      // 들여쓰기는 라벨 위치로 드러난다 (depth0 10 / depth1 20 / depth2 20 + 점 22 + gap 8)
      await expect(iconLeft(rows[0]) - left(rows[0])).toBe(10);
      await expect(iconLeft(rows[1]) - left(rows[1])).toBe(20);
      await expect(iconLeft(rows[2]) - left(rows[2])).toBe(50);
    });

    // 로고는 홈 진입점이다 — 접기 버튼과 나란히 있어도 역할이 다르다
    await expect(canvas.getByRole('link', { name: '홈으로 이동' })).toHaveAttribute('href', '/');

    await userEvent.click(canvas.getByRole('button', { name: '사이드바 접기' }));
    await expect(args.onCollapse).toHaveBeenCalledTimes(1);
  },
};

export const WikiExpanded: Story = {
  args: { onCollapse: fn(), showScrollFade: true },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17859-129060',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17859:129060',
      },
      viewport: { width: 280, height: 1024 },
      states: ['wiki-expanded'],
    }),
  },
  render: (args) => (
    <SideNavShell
      {...args}
      spaceSwitcher={
        <>
          <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" onClick={noop} />
          <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" selected onClick={noop} />
        </>
      }
      primaryItems={
        <>
          <div className="flex flex-col">
            {WIKI_PRIMARY_ITEMS.map((item) => (
              <SnbNavRow key={item.id} {...item} onClick={noop} />
            ))}
          </div>
          <SnbTeamspaceCard name="Acme의 지식 허브" Icon={TEAMSPACE_ICON} hasNotification />
          <div className="flex flex-col">
            {WIKI_DROPDOWN_ITEMS.map((item) => (
              <SnbNavRow key={item.id} {...item} onClick={noop} />
            ))}
          </div>
        </>
      }
      footer={<SnbFooter userName="팀원G" userRole="PM" />}
    >
      <div className="flex flex-col gap-1.5">
        {/* 위키 모드의 트리 섹션명은 "위키"다 (시안 15338:92139) */}
        <SnbSectionHeader label="위키" />
        <NavTree
          nodes={PROJECT_TREE_NODES}
          activeId="channel-1"
          defaultExpandedIds={['channel-1', 'folder-1']}
          onNodeClick={noop}
          onNodeMore={noop}
          onNodeAdd={noop}
        />
      </div>
    </SideNavShell>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('Acme의 지식 허브')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '대시보드' })).toHaveAttribute('aria-current', 'page');
    // 홈에만 있는 섹션은 위키에 없다
    await expect(canvas.queryByText('최근 질문')).toBeNull();
    await expect(canvas.queryByText('에이전트')).toBeNull();
  },
};

export const EmptySectionsNoInventedEmptyState: Story = {
  args: { onCollapse: fn() },
  render: (args) => (
    <SideNavShell
      {...args}
      spaceSwitcher={<SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" selected onClick={noop} />}
      primaryItems={null}
      footer={<SnbFooter userName="팀원G" userRole="PM" />}
    >
      {null}
    </SideNavShell>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const navArea = canvas.getByTestId('side-nav-shell-nav-area');

    // 빈 목록을 받아도 어떤 문구도 만들지 않는다 — 빈 상태 카피는 승인된 시안이 없다
    await expect(navArea.textContent?.replace('홈', '').trim()).toBe('');

    // 넘칠 것이 없는데도 스크롤바 자리는 비어 있다 — 목록이 길어져도 행 폭이 그대로다
    await expect(navArea.scrollHeight).toBeLessThanOrEqual(navArea.clientHeight);
    await expect(navArea.offsetWidth - navArea.clientWidth).toBe(8);
  },
};
