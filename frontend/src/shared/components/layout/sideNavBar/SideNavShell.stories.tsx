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
  title: 'Compositions/Shared/Layout/SideNavShell',
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
        '위키만 스크롤 페이드를 가진다(Figma 실측).',
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
  args: { onCollapse: fn() },
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
            <SnbNavRow key={item.id} {...item} onClick={noop} />
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
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('에이전트')).toBeInTheDocument();
    await expect(canvas.getByText('최근 질문')).toBeInTheDocument();
    await expect(canvas.getByText('프로젝트')).toBeInTheDocument();
    // 트리는 slot으로 들어온다
    await expect(canvas.getByRole('button', { name: '파일명texttexttexttext' })).toBeInTheDocument();
    // 요청됨 배지는 서버 값이다
    await expect(canvas.getByTestId('snb-nav-row-count')).toHaveTextContent('1');

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
        <SnbSectionHeader label="프로젝트" />
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
    await expect(canvas.getByRole('button', { name: '지식 대시보드' })).toHaveAttribute('aria-current', 'page');
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
  },
};
