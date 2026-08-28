import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbRailFooter from './SnbRailFooter';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbRailFooter',
  component: SnbRailFooter,
  tags: ['autodocs'],
  args: { userName: '팀원G', onSettingsClick: fn(), onProfileClick: fn() },
  argTypes: { hasSettingsNotification: { control: 'boolean' } },
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
      viewport: { width: 200, height: 200 },
      states: ['default', 'with-settings-dot'],
      dataNotes: ['설정 알림 점의 발화 조건은 미정이라 표시 여부만 props로 받는다(감사 §5-8).'],
      layoutNotes: ['펼침에서는 설정이 프로필 행 안에 들어간다 — 여기서는 독립 버튼이다.'],
    }),
  },
} satisfies Meta<typeof SnbRailFooter>;

export default meta;

type Story = StoryObj<typeof SnbRailFooter>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-16 flex-col items-center p-2">{children}</div>
);

export const Default: Story = {
  render: (args) => (
    <Frame>
      <SnbRailFooter {...args} />
    </Frame>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByTestId('snb-rail-settings-dot')).toBeNull();
    await userEvent.click(canvas.getByRole('button', { name: '설정' }));
    await expect(args.onSettingsClick).toHaveBeenCalledTimes(1);

    await userEvent.click(canvas.getByRole('button', { name: '팀원G' }));
    await expect(args.onProfileClick).toHaveBeenCalledTimes(1);
  },
};

export const WithSettingsDot: Story = {
  args: { hasSettingsNotification: true },
  render: (args) => (
    <Frame>
      <SnbRailFooter {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByTestId('snb-rail-settings-dot')).toBeInTheDocument();
  },
};
