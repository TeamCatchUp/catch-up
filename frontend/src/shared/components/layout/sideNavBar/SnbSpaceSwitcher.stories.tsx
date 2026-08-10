import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import IconHome from '@/public/icons/icon/home.svg';
import IconStacks from '@/public/icons/icon/stacks.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbSpaceSwitcher',
  component: SnbSpaceSwitcher,
  tags: ['autodocs'],
  args: { Icon: IconHome, label: '홈', selected: true, variant: 'expanded', onClick: fn() },
  argTypes: {
    selected: { control: 'boolean' },
    variant: { control: 'inline-radio', options: ['expanded', 'closed'] },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17895-46180',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17895:46180',
      },
      viewport: { width: 320, height: 200 },
      states: ['expanded-selected', 'expanded-unselected', 'closed-selected', 'closed-unselected'],
      layoutNotes: ['펼침은 선택된 쪽만 라벨을 노출하며 남은 폭을 채운다. 닫힘은 36×36 정사각이다.'],
      reuseNotes: ['홈 ↔ LLM Wiki 두 모드 사이를 오가는 유일한 컨트롤이다.'],
      tokenNotes: [
        '펼침 선택은 Fill/Primary/Normal/Neutral, 미선택은 Fill/Normal/Strong이다.',
        '닫힘 선택 카드는 Fill/Normal/Assistive다 — 라이트에서는 fill-normal-normal과 같은 흰색이라 눈으로 구분되지 않지만 다크에서 갈린다(neutral-83 ↔ neutral-85). play가 클래스로 고정한다.',
      ],
      dataNotes: ['아이콘은 Figma가 filled 변형(icon/home_filled·icon/stacks_filled)을 쓴다 — 자산 확보는 조립 단계 과제다.'],
    }),
  },
} satisfies Meta<typeof SnbSpaceSwitcher>;

export default meta;

type Story = StoryObj<typeof SnbSpaceSwitcher>;

export const ExpandedPair: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal w-56 p-2">
      <div className="flex items-center gap-1.5">
        <SnbSpaceSwitcher {...args} Icon={IconHome} label="홈" selected />
        <SnbSpaceSwitcher {...args} Icon={IconStacks} label="LLM Wiki" selected={false} />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 선택된 쪽만 라벨이 보인다
    await expect(canvas.getByText('홈')).toBeInTheDocument();
    await expect(canvas.queryByText('LLM Wiki')).toBeNull();
    await expect(canvas.getByRole('button', { name: '홈' })).toHaveAttribute('aria-current', 'page');
    // 미선택도 접근 이름은 남는다
    await expect(canvas.getByRole('button', { name: 'LLM Wiki' })).toBeInTheDocument();

    // 펼침 미선택 아이콘은 Icon/Normal/Alternative다 — 닫힘(Neutral)보다 한 단계 옅다
    await expect(canvas.getByRole('button', { name: '홈' }).querySelector('svg')).toHaveClass(
      'text-icon-normal-strong',
    );
    await expect(canvas.getByRole('button', { name: 'LLM Wiki' }).querySelector('svg')).toHaveClass(
      'text-icon-normal-alternative',
    );
  },
};

export const ExpandedPairWikiSelected: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal w-56 p-2">
      <div className="flex items-center gap-1.5">
        <SnbSpaceSwitcher {...args} Icon={IconHome} label="홈" selected={false} />
        <SnbSpaceSwitcher {...args} Icon={IconStacks} label="LLM Wiki" selected />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('LLM Wiki')).toBeInTheDocument();
    await expect(canvas.queryByText('홈')).toBeNull();
    // 선택된 쪽이 남은 폭을 차지한다
    const home = canvas.getByRole('button', { name: '홈' });
    const wiki = canvas.getByRole('button', { name: 'LLM Wiki' });
    await expect(wiki.getBoundingClientRect().width).toBeGreaterThan(home.getBoundingClientRect().width);
  },
};

export const ClosedPair: Story = {
  args: { variant: 'closed' },
  render: (args) => (
    <div className="bg-fill-normal-normal w-16 p-2">
      <div className="flex flex-col items-center gap-1">
        <SnbSpaceSwitcher {...args} Icon={IconHome} label="홈" selected />
        <SnbSpaceSwitcher {...args} Icon={IconStacks} label="LLM Wiki" selected={false} />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 닫힘에서는 라벨이 보이지 않지만 접근 이름은 남는다
    await expect(canvas.getByRole('button', { name: 'LLM Wiki' })).toBeInTheDocument();
    await expect(canvas.queryByText('LLM Wiki')).toBeNull();

    // 두 칸 모두 36×36 정사각이다
    const home = canvas.getByRole('button', { name: '홈' });
    await expect(Math.round(home.getBoundingClientRect().width)).toBe(36);
    await expect(Math.round(home.getBoundingClientRect().height)).toBe(36);

    // 닫힘 미선택 아이콘은 Icon/Normal/Neutral — 펼침(Alternative)과 다르다
    await expect(canvas.getByRole('button', { name: 'LLM Wiki' }).querySelector('svg')).toHaveClass(
      'text-icon-normal-neutral',
    );

    // 선택 카드 배경은 Fill/Normal/Assistive다. 라이트에서 fill-normal-normal과
    // 같은 흰색이라 렌더로는 구분되지 않으니 클래스로 고정한다 — 다크에서 갈린다
    await expect(home).toHaveClass('bg-fill-normal-assistive');
  },
};
