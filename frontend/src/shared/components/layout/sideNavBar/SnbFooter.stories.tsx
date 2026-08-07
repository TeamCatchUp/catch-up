import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbFooter from './SnbFooter';

const meta = {
  title: 'Compositions/Shared/Layout/SnbFooter',
  component: SnbFooter,
  tags: ['autodocs'],
  args: {
    userName: '팀원G',
    userRole: 'PM',
    onNewClick: fn(),
    onProfileClick: fn(),
    onSettingsClick: fn(),
  },
  argTypes: { userName: { control: 'text' }, userRole: { control: 'text' } },
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
      viewport: { width: 320, height: 200 },
      states: ['default', 'long-user-name'],
      layoutNotes: ['설정 버튼이 프로필 행 안에 있다 — 닫힘 상태에서는 Rail 하단에 독립으로 놓인다.'],
      dataNotes: ['아바타 이미지는 아직 계약이 없어 기본 프로필 아이콘을 쓴다.'],
    }),
  },
} satisfies Meta<typeof SnbFooter>;

export default meta;

type Story = StoryObj<typeof SnbFooter>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-60">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbFooter {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '신규' }));
    await expect(args.onNewClick).toHaveBeenCalledTimes(1);

    await userEvent.click(canvas.getByRole('button', { name: '설정' }));
    await expect(args.onSettingsClick).toHaveBeenCalledTimes(1);
    // 설정 버튼이 프로필 행 안에 있어도 클릭이 프로필로 새면 안 된다
    await expect(args.onProfileClick).not.toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: /팀원G/ }));
    await expect(args.onProfileClick).toHaveBeenCalledTimes(1);
  },
};

export const LongUserName: Story = {
  args: { userName: '아주 긴 사용자 이름이 들어가는 경우', userRole: '프로덕트 매니저' },
  render: (args) => (
    <Frame>
      <SnbFooter {...args} />
    </Frame>
  ),
};
