import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import MappingFilterChips from './MappingFilterChips';

const meta = {
  title: 'Compositions/Admin/Integrations/User Mapping/MappingFilterChips',
  component: MappingFilterChips,
  tags: ['autodocs'],
  args: { value: 'all', onChange: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17379-78312',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17379:78312',
      },
      viewport: { width: 600, height: 100 },
      states: ['default', 'channel-talk'],
      dataNotes: [
        '값은 API status 필터와 1:1 (all/full/partial).',
        '칩 마스터 라벨은 ✏️ Value 플레이스홀더 — 라벨은 화면 실측(전체 이용자/전체 연동됨/일부 미연동).',
        '커넥터 칩은 채널톡 하나만 고정이다(사용자 결정 2026-08-04) — 통계 카드는 표시 전용이라 칩을 만들지 않는다.',
        '채널톡은 상태 필터가 아니라 표를 1열로 좁히는 뷰 필터다 — 조회는 all 로 나간다.',
      ],
    }),
  },
} satisfies Meta<typeof MappingFilterChips>;

export default meta;

type Story = StoryObj<typeof MappingFilterChips>;

export const Default: Story = {
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('tab', { name: '전체 이용자' })).toHaveAttribute('aria-selected', 'true');

    await userEvent.click(canvas.getByRole('tab', { name: '일부 미연동' }));
    await expect(args.onChange).toHaveBeenCalledWith('partial');
  },
};

/** 채널톡 — 상태 필터가 아니라 표를 1열로 좁히는 고정 뷰 필터 */
export const ChannelTalk: Story = {
  args: { value: 'channel_talk' },
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('tab', { name: '채널톡' })).toHaveAttribute('aria-selected', 'true');
    await expect(canvas.getByRole('tab', { name: '전체 이용자' })).toHaveAttribute('aria-selected', 'false');

    await userEvent.click(canvas.getByRole('tab', { name: '전체 이용자' }));
    await expect(args.onChange).toHaveBeenCalledWith('all');
  },
};
