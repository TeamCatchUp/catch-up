'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { Avatar, type AvatarSize } from './avatar';

const SIZES: readonly AvatarSize[] = ['xsmall', 'small', 'medium', 'large', 'xlarge'];

/** size별 지름(px). 스토리 어서션의 기대값이다. */
const SIZE_PX: Record<AvatarSize, number> = {
  xsmall: 20,
  small: 25,
  medium: 28,
  large: 30,
  xlarge: 40,
};

const meta = {
  title: 'Primitives/Shared/Avatar',
  component: Avatar,
  tags: ['autodocs'],
  args: {
    size: 'small',
    src: null,
    alt: '',
  },
  argTypes: {
    size: {
      control: 'inline-radio',
      options: SIZES,
    },
    src: { control: 'text' },
    alt: { control: 'text' },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=582-2674',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '582:2674',
      },
      viewport: { width: 480, height: 240 },
      states: ['default', 'with-image', 'fallback', 'unsafe-url', 'all-sizes'],
      reuseNotes: [
        'Figma `imagebox/profile`(componentSet 582:2674)의 stack=1 변형에 대응한다.',
        'size 5종은 Figma에 정의된 전부이고, `default_profile.svg`를 개별 import하던 17곳의 크기와 일치한다.',
        '56px(SelectedUserProfile)·70px(MemberProfileCard) 2곳은 Figma에 대응 variant가 없어 제외했다 — 디자이너 확인 대상.',
      ],
      dataNotes: [
        'src가 비었거나 http(s)가 아니면 기본 프로필로 폴백한다. 가드는 shared/utils/isSafeUrl.',
        'hover·pressed는 아바타 단독으로는 시안에 없다 — 상태는 AvatarGroup의 pill이 갖는다.',
      ],
      tokenNotes: [
        '링 1px = Figma stroke `Fill/Normal/Strong`(#F7F7F8) → border-fill-normal-strong.',
        'radius 1000 → rounded-full.',
      ],
    }),
  },
} satisfies Meta<typeof Avatar>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const AllSizes: Story = {
  render: () => (
    <div className="bg-fill-normal-normal flex items-end gap-6 p-6">
      {SIZES.map((size) => (
        <div key={size} data-testid={`avatar-${size}`} className="flex flex-col items-center gap-2">
          <Avatar size={size} />
          <span className="text-body-xsmall text-text-normal-alternative">
            {size} · {SIZE_PX[size]}px
          </span>
        </div>
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 인접 size는 눈으로 구분할 수 없다 — 지름을 직접 잰다.
    for (const size of SIZES) {
      const avatar = canvas.getByTestId(`avatar-${size}`).firstElementChild;
      await expect(avatar).not.toBeNull();

      const rect = (avatar as HTMLElement).getBoundingClientRect();
      await expect(Math.round(rect.width)).toBe(SIZE_PX[size]);
      await expect(Math.round(rect.height)).toBe(SIZE_PX[size]);
    }
  },
};

export const WithImage: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex items-center gap-4 p-6">
      {/* 정적 자산을 절대 URL로 만든다 — isSafeUrl이 http(s)만 통과시킨다. */}
      <Avatar {...args} src={new URL('/image/auth/catchup-login.png', window.location.origin).href} />
      <span className="text-body-small text-text-normal-normal">이미지가 있으면 img로 렌더</span>
    </div>
  ),
  args: {
    size: 'xlarge',
    alt: '김캐치',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const image = canvas.getByRole('img', { name: '김캐치' });
    await expect(image.tagName).toBe('IMG');
    await expect(image).toHaveClass('object-cover');
  },
};

export const UnsafeUrlFallsBack: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex items-center gap-4 p-6">
      <Avatar {...args} />
      <span className="text-body-small text-text-normal-normal">위험 스킴은 기본 프로필로 폴백</span>
    </div>
  ),
  args: {
    size: 'xlarge',
    src: 'javascript:alert(1)',
    alt: '박캐치',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // img가 아예 렌더되지 않아야 한다. 이름은 sr-only 텍스트로만 남는다.
    await expect(canvas.queryByRole('img')).toBeNull();
    await expect(canvas.getByText('박캐치')).toBeInTheDocument();

    // 폴백 아이콘이 실제로 그려졌는지 본다.
    await expect(canvasElement.querySelector('svg')).not.toBeNull();
  },
};
