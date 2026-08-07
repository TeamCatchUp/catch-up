import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SideNavRail from './SideNavRail';
import { HOME_RAIL_ITEMS, SPACE_HOME_ICON, SPACE_WIKI_ICON, WIKI_RAIL_ITEMS } from './snbNavFixtures';
import SnbRailFooter from './SnbRailFooter';
import SnbRailItem from './SnbRailItem';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Shell/SideNavRail',
  component: SideNavRail,
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17859-129063',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17859:129063',
      },
      viewport: { width: 120, height: 1024 },
      states: ['home-collapsed-TBD', 'wiki-collapsed-TBD'],
      dataNotes: [
        '메뉴 구성이 펼침과 불일치한다 — 어느 쪽이 맞는지 미결이라 스토리 이름에 TBD를 남긴다(설계 §7-1).',
        '셸은 목록을 props로 받으므로 구성을 코드가 정하지 않는다.',
      ],
      layoutNotes: ['닫힘에는 즐겨찾기·최근 질문·프로젝트 트리가 없다 — 이것도 의도인지 미결이다.'],
    }),
  },
} satisfies Meta<typeof SideNavRail>;

export default meta;

type Story = StoryObj<typeof SideNavRail>;

const noop = () => {};

export const HomeCollapsedMenuCompositionTBD: Story = {
  args: { onExpand: fn() },
  render: (args) => (
    <SideNavRail
      {...args}
      spaceSwitcher={
        <>
          <SnbSpaceSwitcher variant="closed" Icon={SPACE_HOME_ICON} label="홈" selected onClick={noop} />
          <SnbSpaceSwitcher variant="closed" Icon={SPACE_WIKI_ICON} label="LLM Wiki" onClick={noop} />
        </>
      }
      footer={<SnbRailFooter userName="팀원G" />}
    >
      {HOME_RAIL_ITEMS.map((item) => (
        <SnbRailItem key={item.id} {...item} onClick={noop} />
      ))}
    </SideNavRail>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: '문서 탐색' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '히스토리' })).toBeInTheDocument();
    // 닫힘에는 프로젝트 트리가 없다
    await expect(canvas.queryByText('프로젝트')).toBeNull();

    await step('Divider 위아래 간격이 다르다 — 눈으로는 놓치기 쉬워 값으로 고정한다', async () => {
      const nav = canvasElement.querySelector('nav')!;
      const divider = canvasElement.querySelector('[data-slot="side-nav-rail-divider"]')!;
      const switcherBox = divider.previousElementSibling!;
      const itemList = divider.nextElementSibling!;
      const box = (el: Element) => el.getBoundingClientRect();

      await expect(Math.round(box(nav).width)).toBe(64);
      await expect(Math.round(box(divider).top - box(switcherBox).bottom)).toBe(20);
      await expect(Math.round(box(itemList).top - box(divider).bottom)).toBe(12);
      await expect(Math.round(box(divider).width)).toBe(20);
      await expect(Math.round(box(itemList.children[0]).height)).toBe(57);
    });

    await userEvent.click(canvas.getByRole('button', { name: '사이드바 펼치기' }));
    await expect(args.onExpand).toHaveBeenCalledTimes(1);
  },
};

export const WikiCollapsedMenuCompositionTBD: Story = {
  args: { onExpand: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17859-129064',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17859:129064',
      },
      viewport: { width: 120, height: 1024 },
      states: ['wiki-collapsed-TBD'],
    }),
  },
  render: (args) => (
    <SideNavRail
      {...args}
      spaceSwitcher={
        <>
          <SnbSpaceSwitcher variant="closed" Icon={SPACE_HOME_ICON} label="홈" onClick={noop} />
          <SnbSpaceSwitcher variant="closed" Icon={SPACE_WIKI_ICON} label="LLM Wiki" selected onClick={noop} />
        </>
      }
      footer={<SnbRailFooter userName="팀원G" />}
    >
      {WIKI_RAIL_ITEMS.map((item) => (
        <SnbRailItem key={item.id} {...item} onClick={noop} />
      ))}
    </SideNavRail>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: '지식 관리' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '콘텐츠' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '요청됨' })).toHaveAttribute('aria-current', 'page');
    // 펼침에 있는 새 채팅이 닫힘에는 없다 — 불일치를 스토리가 드러낸다
    await expect(canvas.queryByRole('button', { name: '새 채팅' })).toBeNull();
  },
};
