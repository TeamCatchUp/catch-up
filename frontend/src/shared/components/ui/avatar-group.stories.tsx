'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { AvatarGroup, type AvatarGroupItem } from './avatar-group';

const PARTICIPANTS: readonly AvatarGroupItem[] = [
  { alt: '김캐치' },
  { alt: '이업' },
  { alt: '박위키' },
  { alt: '최문서' },
  { alt: '정검토' },
];

const meta = {
  title: 'Primitives/Shared/AvatarGroup',
  component: AvatarGroup,
  tags: ['autodocs'],
  args: {
    avatars: PARTICIPANTS.slice(0, 3),
    size: 'small',
  },
  argTypes: {
    size: { control: 'inline-radio', options: ['small', 'medium'] },
    max: { control: { type: 'number', min: 1, max: 5 } },
    totalLabel: { control: 'text' },
    disabled: { control: 'boolean' },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17849-106441',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17849:106441',
      },
      viewport: { width: 480, height: 240 },
      states: ['stack-2', 'stack-3', 'overflow-chip', 'with-total-label', 'interactive', 'disabled'],
      reuseNotes: [
        '겹침 스택은 Figma `imagebox/profile`의 stack 변형(582:2674), pill은 `Group Button`(961:5913)이다.',
        'Figma가 stack 변형을 small(25)·medium(28)로만 정의해 size도 두 종뿐이다.',
        'LLM Wiki 문서 메인의 참여자 그룹(17849:106441)이 이 조합의 첫 소비처 시안이다.',
      ],
      dataNotes: [
        '아바타 목록·총원 라벨 모두 props다. 참여자 API가 아직 없어 화면 장착은 별도 작업이다.',
        'onClick을 주면 pill이 button이 된다 — 시안에 상태 4종이 있을 뿐 클릭 동작은 정의돼 있지 않다.',
      ],
      layoutNotes: [
        '겹침 -6px, 최대 3개 표시 후 "+N" 칩. 둘 다 Figma `stack=3 이상` 변형의 실측값이다.',
        'pill 높이 36px은 시안 고정값이고 폭은 hug(w-fit)이라 라벨 길이를 따라간다.',
      ],
      tokenNotes: [
        'pill 배경 #F7F7F8 → bg-fill-normal-strong, 테두리 #E1E2E4 → border-line-normal-normal.',
        'hover 6% / pressed 10% / inactive 3% → fill-normal-interaction-{hover,pressed,inactive} (알파 전환 후 값과 일치).',
        '"+N" 칩 그림자는 Figma Shadow/Button(0 4px 8px rgba(0,0,0,.15))이지만 코드 --shadow-button은 0 0 4px rgba(0,0,0,.08)이다 — 드리프트, 디자이너 확인 대상.',
      ],
      interactionNotes: ['hover·pressed는 CSS 상태라 스토리로 고정하지 않는다(Playwright hover로만 실측 가능).'],
    }),
  },
} satisfies Meta<typeof AvatarGroup>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const StackOnly: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex flex-col gap-6 p-6">
      <div data-testid="stack-2" className="flex items-center gap-4">
        <AvatarGroup {...args} avatars={PARTICIPANTS.slice(0, 2)} />
        <span className="text-body-small text-text-normal-alternative">stack=2</span>
      </div>
      <div data-testid="stack-3" className="flex items-center gap-4">
        <AvatarGroup {...args} avatars={PARTICIPANTS.slice(0, 3)} />
        <span className="text-body-small text-text-normal-alternative">stack=3</span>
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 겹침은 눈으로 셀 수 없다 — 인접 아바타의 x 간격을 잰다.
    const stack = canvas.getByTestId('stack-3').firstElementChild?.firstElementChild as HTMLElement;
    const [first, second, third] = Array.from(stack.children) as HTMLElement[];

    await expect(Math.round(second.getBoundingClientRect().x - first.getBoundingClientRect().x)).toBe(19);
    await expect(Math.round(third.getBoundingClientRect().x - second.getBoundingClientRect().x)).toBe(19);

    // 아바타 3개가 겹친 스택의 전체 폭
    await expect(Math.round(stack.getBoundingClientRect().width)).toBe(63);
  },
};

export const OverflowChip: Story = {
  args: {
    avatars: PARTICIPANTS,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 5명 중 3명만 보이고 나머지는 칩으로 접힌다.
    await expect(canvas.getByText('+2')).toBeInTheDocument();
  },
};

export const WithTotalLabel: Story = {
  name: '시안 재현 (참여자 12명)',
  args: {
    avatars: PARTICIPANTS,
    totalLabel: '12명',
  },
  render: (args) => (
    <div className="bg-fill-normal-normal p-6">
      <div data-testid="pill-wrap" className="w-fit">
        <AvatarGroup {...args} />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const pill = canvas.getByTestId('pill-wrap').firstElementChild as HTMLElement;

    // 폭은 라벨 글꼴 폭을 타므로 높이만 고정값으로 검사한다.
    await expect(Math.round(pill.getBoundingClientRect().height)).toBe(36);

    await expect(canvas.getByText('12명')).toBeInTheDocument();
    await expect(canvas.getByText('+2')).toBeInTheDocument();

    // 정적 pill은 버튼이 아니다 — 클릭 동작이 없는데 버튼으로 보이면 오독이다.
    await expect(canvas.queryByRole('button')).toBeNull();
  },
};

export const Interactive: Story = {
  args: {
    avatars: PARTICIPANTS,
    totalLabel: '12명',
    onClick: fn(),
    'aria-label': '참여자 12명 보기',
  },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);

    const button = canvas.getByRole('button', { name: '참여자 12명 보기' });
    await userEvent.click(button);
    await expect(args.onClick).toHaveBeenCalledTimes(1);
  },
};

export const Disabled: Story = {
  args: {
    avatars: PARTICIPANTS,
    totalLabel: '12명',
    onClick: fn(),
    disabled: true,
    'aria-label': '참여자 12명 보기',
  },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);

    const button = canvas.getByRole('button', { name: '참여자 12명 보기' });
    await expect(button).toBeDisabled();

    await userEvent.click(button);
    await expect(args.onClick).not.toHaveBeenCalled();
  },
};

export const MediumSize: Story = {
  args: {
    avatars: PARTICIPANTS,
    size: 'medium',
    totalLabel: '12명',
  },
  render: (args) => (
    <div className="bg-fill-normal-normal p-6">
      <div data-testid="pill-wrap" className="w-fit">
        <AvatarGroup {...args} />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const stack = canvas.getByTestId('pill-wrap').firstElementChild?.firstElementChild as HTMLElement;
    const [first, second] = Array.from(stack.children) as HTMLElement[];

    await expect(Math.round(first.getBoundingClientRect().width)).toBe(28);
    // 겹침은 size와 무관하게 고정이다
    await expect(Math.round(second.getBoundingClientRect().x - first.getBoundingClientRect().x)).toBe(22);
  },
};
