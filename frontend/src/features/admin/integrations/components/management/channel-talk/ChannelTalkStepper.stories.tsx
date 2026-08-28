import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ChannelTalkStepper from './ChannelTalkStepper';

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkStepper',
  component: ChannelTalkStepper,
  tags: ['autodocs'],
  args: { current: 'connect', onStepChange: fn(), onBack: fn() },
  argTypes: {
    current: { control: 'inline-radio', options: ['connect', 'embed'] },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17363-100283',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17363:100283',
      },
      viewport: { width: 716, height: 100 },
      states: ['step-1', 'step-2'],
      layoutNotes: ['숫자 칩 24, 라벨 x40, 단계 사이 icon/arrow_right2 24. 우측에 임베딩 관리로 돌아가는 링크.'],
    }),
  },
} satisfies Meta<typeof ChannelTalkStepper>;

export default meta;

type Story = StoryObj<typeof ChannelTalkStepper>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Step1: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkStepper {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('채널 연결 관리')).toBeInTheDocument();
    await expect(canvas.getByText('임베딩하기')).toBeInTheDocument();

    // 현재 단계를 스크린리더에도 알린다
    await expect(canvas.getByText('채널 연결 관리').closest('li')).toHaveAttribute('aria-current', 'step');

    // 다음 단계로 건너뛴다 — 하단 바 [임베딩하기]와 같이 활성 조건이 없다.
    // 숫자 칩은 aria-hidden이라(순서는 ol이 이미 알린다) 접근성 이름은 라벨뿐이다
    await userEvent.click(canvas.getByRole('button', { name: '임베딩하기' }));
    await expect(args.onStepChange).toHaveBeenCalledWith('embed');

    await userEvent.click(canvas.getByRole('button', { name: /임베딩 관리로/ }));
    await expect(args.onBack).toHaveBeenCalled();
  },
};

export const Step2: Story = {
  args: { current: 'embed' },
  render: (args) => (
    <Frame>
      <ChannelTalkStepper {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('임베딩하기').closest('li')).toHaveAttribute('aria-current', 'step');
    await expect(canvas.getByText('채널 연결 관리').closest('li')).not.toHaveAttribute('aria-current');

    // 되돌아가기 — 하단 바에는 ②→① 경로가 없어 스텝퍼가 유일하다
    await userEvent.click(canvas.getByRole('button', { name: '채널 연결 관리' }));
    await expect(args.onStepChange).toHaveBeenCalledWith('connect');
  },
};
