import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingHistoryTable from './EmbeddingHistoryTable';

const ITEMS = [
  { id: 'f1', target: '채널명 A', status: 'failed' as const, executedAt: '2026.03.18 00:00 PM', failureCount: 10 },
  { id: 'f2', target: '채널명 B', status: 'failed' as const, executedAt: '2026.03.18 00:00 PM', failureCount: 123456 },
  { id: 's1', target: '채널명 C', status: 'success' as const, executedAt: '2026.03.18 00:00 PM' },
  { id: 's2', target: '채널명 D', status: 'success' as const, executedAt: '2026.03.18 00:00 PM' },
];

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/EmbeddingHistoryTable',
  component: EmbeddingHistoryTable,
  tags: ['autodocs'],
  args: { service: 'slack', items: ITEMS, onRetry: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17071-112226',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17071:112226',
      },
      viewport: { width: 716, height: 560 },
      states: ['all', 'success-only', 'failed-only', 'empty', 'narrow'],
      layoutNotes: [
        '필터는 Tab 158×36 = Chips 50 ×3 + gap 4 ×2. 회색 트랙이 없는 낱개 칩이라 Chip variant="outline"을 쓴다.',
        '표는 <table> 엘리먼트에 행 grid. 716 = 12 | 대상(1fr) | 16 | 150 | 16 | 150 | 16 | 32 | 12.',
        '진행중 표와 열 x가 같아야 해서 폭을 내용에 맡기지 않는다 — 템플릿은 embeddingTableGrid.ts 하나뿐이다.',
      ],
      dataNotes: [
        '필터 라벨은 현행과 같은 전체/성공/실패다.',
        'Figma Chips의 건수 배지(0:4)와 실패 빨간 점(0:5) 레이어는 이 인스턴스에서 hidden이라 뺐다 — 미결 #18.',
      ],
    }),
  },
} satisfies Meta<typeof EmbeddingHistoryTable>;

export default meta;

type Story = StoryObj<typeof EmbeddingHistoryTable>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const All: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('임베딩 히스토리')).toBeInTheDocument();
    await expect(canvas.getByRole('tab', { name: '전체' })).toHaveAttribute('aria-selected', 'true');
    await expect(canvas.getAllByRole('row')).toHaveLength(5); // 헤더 1 + 본문 4

    await userEvent.click(canvas.getAllByRole('button', { name: '임베딩 재시도' })[0]);
    await expect(args.onRetry).toHaveBeenCalledWith('f1');
  },
};

export const SuccessOnly: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('tab', { name: '성공' }));
    await expect(canvas.getAllByRole('row')).toHaveLength(3); // 헤더 1 + 성공 2
    // '실패'는 필터 탭 라벨과 겹치므로 재시도 버튼 유무로 본다
    await expect(canvas.queryByRole('button', { name: '임베딩 재시도' })).not.toBeInTheDocument();
  },
};

export const FailedOnly: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('tab', { name: '실패' }));
    await expect(canvas.getAllByRole('row')).toHaveLength(3); // 헤더 1 + 실패 2
    await expect(canvas.getByText('50,000+건')).toBeInTheDocument();
  },
};

/**
 * 선택 칩만 흰 배경 + 테두리를 갖는다. 회색 트랙 위 세그먼티드 컨트롤이 아니다.
 * Figma `17169:75982` — Chips 50×36, gap 4.
 */
export const FilterChips: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const all = canvas.getByRole('tab', { name: '전체' });
    const success = canvas.getByRole('tab', { name: '성공' });

    // 미선택 칩은 배경도 테두리도 없다
    const idle = getComputedStyle(success);
    await expect(idle.borderTopColor).toBe('rgba(0, 0, 0, 0)');
    await expect(idle.backgroundColor).toBe('rgba(0, 0, 0, 0)');

    // 선택 칩은 흰 배경 + line/normal/strong (#dbdcdf) 테두리
    const active = getComputedStyle(all);
    await expect(active.borderTopColor).toBe('rgb(219, 220, 223)');
    await expect(active.backgroundColor).toBe('rgb(255, 255, 255)');

    // 칩 높이 36
    await expect(all.getBoundingClientRect().height).toBe(36);

    // 선택이 옮겨가도 폭이 흔들리지 않는다 — 두 상태 모두 px-3 + border
    const widthBefore = success.getBoundingClientRect().width;
    await userEvent.click(success);
    await expect(success.getBoundingClientRect().width).toBe(widthBefore);
  },
};

export const Empty: Story = {
  args: { items: [] },
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 빈 상태 문구는 현행 코드에서 승계한다 — Figma에 근거가 없다
    await expect(canvas.getByText('임베딩 히스토리가 없습니다.')).toBeInTheDocument();
  },
};

/**
 * Figma 716의 75% 슬롯(536). 상태 150 · 시각 150 · 액션 32는 그대로 두고
 * 대상 열(1fr)만 132로 줄어 truncate 된다.
 *
 * 하한은 404다 — 고정 열 332 + gap 48 + padding 24. 그 아래는 어떤 방식으로도
 * 안 줄어들어서 `overflow-x-auto`로 흘린다.
 */
export const Narrow: Story = {
  args: {
    // 대상 열이 실제로 잘리는지 보려면 132보다 긴 이름이 필요하다
    items: ITEMS.slice(0, 2).map((item) => ({ ...item, target: `${item.target} text text text text text text` })),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal w-140 p-3">
      <EmbeddingHistoryTable {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const table = canvas.getByRole('table');
    const scroller = table.parentElement as HTMLElement;

    // 가로 스크롤 없음 — 표가 슬롯에 맞춰 줄어든다.
    // 1px 여유는 열 4개의 소수점 폭이 scrollWidth 반올림에서 합쳐진 값이다(실제 넘침 아님)
    await expect(scroller.scrollWidth).toBeLessThanOrEqual(scroller.clientWidth + 1);

    // 헤더 라벨이 두 줄로 접히면 36을 넘는다
    await expect(canvas.getAllByRole('row')[0].getBoundingClientRect().height).toBe(36);

    // 실행 시각이 줄바꿈되면 행이 46을 넘는다
    for (const row of canvas.getAllByRole('row').slice(1)) {
      await expect(row.getBoundingClientRect().height).toBeLessThanOrEqual(48);
    }

    // 대상 이름이 잘려서 표시된다 — 줄어드는 건 대상 열뿐
    const name = canvas.getAllByText(/^채널명/)[0];
    await expect(name.scrollWidth).toBeGreaterThan(name.clientWidth);
  },
};
