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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17379-78313',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17379:78313',
      },
      viewport: { width: 600, height: 100 },
      states: ['default', 'channel-talk', 'interaction'],
      layoutNotes: [
        '낱개 칩이 아니라 세그먼티드 컨트롤이다 — 트랙 fill/normal/strong + line/normal/neutral 1px + radius 8, padding·gap 2.',
        '칩 h32 · padding 8/10 · radius 7. 선택 칩만 흰 배경 + line/normal/assistive 테두리.',
        'hover·pressed 는 임베딩 관리/현황 탭과 동일(사용자 지시) — Figma 가 두 상태를 같은 6%로 둔다.',
      ],
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

/**
 * Figma 실측 대조 — 트랙과 칩의 배경·테두리·높이.
 *
 * hover·pressed 색은 여기서 확인하지 않는다. 스토리 러너의 `userEvent.hover` 는
 * 이벤트만 쏘고 실제 포인터를 옮기지 않아 CSS `:hover` 가 걸리지 않는다 —
 * 그 둘은 Playwright 로 실제 마우스를 움직여 측정했다(임베딩 탭과 같은 값).
 */
export const Interaction: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const track = canvas.getByRole('tablist');
    const selected = canvas.getByRole('tab', { name: '전체 이용자' });
    const idle = canvas.getByRole('tab', { name: '채널톡' });

    // 트랙 — fill/normal/strong + line/normal/neutral
    const trackStyle = getComputedStyle(track);
    await expect(trackStyle.backgroundColor).toBe('rgb(247, 247, 248)');
    await expect(trackStyle.borderTopColor).toBe('rgb(234, 235, 236)');

    // 선택 칩 — 흰 배경 + line/normal/assistive, 높이 32
    const selStyle = getComputedStyle(selected);
    await expect(selStyle.backgroundColor).toBe('rgb(255, 255, 255)');
    await expect(selStyle.borderTopColor).toBe('rgb(244, 244, 245)');
    await expect(selected.getBoundingClientRect().height).toBe(32);

    // 미선택 — 배경 없음. 테두리는 투명이라 선택으로 바뀌어도 폭이 안 튄다
    const idleStyle = getComputedStyle(idle);
    await expect(idleStyle.backgroundColor).toBe('rgba(0, 0, 0, 0)');
    await expect(idleStyle.borderTopColor).toBe('rgba(0, 0, 0, 0)');
    await expect(idleStyle.borderTopWidth).toBe(selStyle.borderTopWidth);
  },
};
