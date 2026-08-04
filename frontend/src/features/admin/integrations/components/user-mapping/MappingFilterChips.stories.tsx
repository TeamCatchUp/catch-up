import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import MappingFilterChips from './MappingFilterChips';

const meta = {
  title: 'Compositions/Admin/Integrations/User Mapping/MappingFilterChips',
  component: MappingFilterChips,
  tags: ['autodocs'],
  args: { value: 'all', onChange: fn(), onClearSource: fn() },
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
      states: ['default', 'source-active'],
      dataNotes: [
        '값은 API status 필터와 1:1 (all/full/partial).',
        '칩 마스터 라벨은 ✏️ Value 플레이스홀더 — 라벨은 화면 실측(전체 이용자/전체 연동됨/일부 미연동).',
        '커넥터 칩은 통계 카드 탭이 만들고, 다시 누르면 해제.',
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

/** 통계 카드 탭으로 커넥터 필터가 걸린 상태 — 커넥터 칩이 선택을 가져간다 */
export const SourceActive: Story = {
  args: { sourceLabel: '채널톡' },
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    const source = canvas.getByRole('tab', { name: '채널톡' });
    await expect(source).toHaveAttribute('aria-selected', 'true');
    await expect(canvas.getByRole('tab', { name: '전체 이용자' })).toHaveAttribute('aria-selected', 'false');

    await userEvent.click(source);
    await expect(args.onClearSource).toHaveBeenCalled();
  },
};
