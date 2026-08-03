import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddedResourceTable from './EmbeddedResourceTable';

const ROWS = Array.from({ length: 4 }, (_, i) => ({
  id: `row-${i}`,
  name: `채널명 text text text text text text text text text ${i}`,
  dataRange: '2000.00.00 - 2000.00.00',
}));

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/EmbeddedResourceTable',
  component: EmbeddedResourceTable,
  tags: ['autodocs'],
  args: { service: 'slack', label: '임베딩된 채널', rows: ROWS },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17071-111748',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17071:111748',
      },
      viewport: { width: 716, height: 400 },
      states: ['rows', 'empty', 'channel-talk-hierarchy', 'long-name'],
      layoutNotes: [
        '표 716, 헤더 36, 행 46. 716 = 12 | 대상(1fr) 496 | 16 | 범위 180 | 12.',
        '<table> 엘리먼트에 행 grid. 범위는 Figma에서 hug지만 행마다 grid가 따로라 auto로 두면 헤더가 어긋난다.',
        'Narrow 스토리가 320 슬롯에서 줄바꿈·가로 넘침이 없는지 지킨다.',
      ],
      dataNotes: ['Figma는 9행 고정이고 페이지네이션이 없다 — 현행 Pagination 유지 여부는 계획 ④에서 정한다.'],
    }),
  },
} satisfies Meta<typeof EmbeddedResourceTable>;

export default meta;

type Story = StoryObj<typeof EmbeddedResourceTable>;

/** Figma 기준 폭 재현 — 패널 780 안에 좌우 32 여백, 표는 정확히 716 */
const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195 px-8 py-6">{children}</div>
);

export const Rows: Story = {
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('임베딩된 채널')).toBeInTheDocument();
    await expect(canvas.getByText('데이터 범위')).toBeInTheDocument();

    const rows = canvas.getAllByRole('row');
    await expect(rows).toHaveLength(5); // 헤더 1 + 본문 4

    // 행 46 + 묶음 사이 간격 2. 날짜가 줄바꿈되면 69를 넘으므로 48로 잡으면 잡힌다
    for (const row of rows.slice(1)) {
      await expect(row.getBoundingClientRect().height).toBeLessThanOrEqual(48);
    }
  },
};

export const Empty: Story = {
  args: { rows: [] },
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 표 대신 빈 상태로 통째로 교체된다
    await expect(canvas.getByText('임베딩한 채널이 없습니다')).toBeInTheDocument();
    await expect(canvas.queryByRole('table')).not.toBeInTheDocument();
  },
};

/**
 * 채널톡만 채널 → 도큐먼트 스페이스 2단 계층이다.
 * Figma `17169:75856` — 도큐먼트 행은 x22로 들여쓰고 로고 대신 icon/connector 를 놓는다.
 */
export const ChannelTalkHierarchy: Story = {
  args: {
    service: 'channel_talk',
    label: '임베딩된 채널',
    rows: [
      {
        id: 'ch-1',
        name: '채널명 text text text text text text text text text',
        dataRange: '2000.00.00 - 2000.00.00',
        children: [
          { id: 'ds-1', name: '도큐먼트 스페이스명 text text text text text', dataRange: '2000.00.00 - 2000.00.00' },
          { id: 'ds-2', name: '도큐먼트 스페이스명 text text text text text', dataRange: '2000.00.00 - 2000.00.00' },
        ],
      },
      {
        id: 'ch-2',
        name: '채널명 text text text text text text text text text',
        dataRange: '2000.00.00 - 2000.00.00',
        children: [
          { id: 'ds-3', name: '도큐먼트 스페이스명 text text text text text', dataRange: '2000.00.00 - 2000.00.00' },
        ],
      },
      { id: 'ch-3', name: '도큐먼트가 없는 채널', dataRange: '2000.00.00 - 2000.00.00' },
    ],
  },
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 헤더 1 + 채널 3 + 도큐먼트 3
    const rows = canvas.getAllByRole('row');
    await expect(rows).toHaveLength(7);

    // 채널 묶음마다 tbody 하나 — 계층이 구조로도 드러나야 한다
    await expect(canvasElement.querySelectorAll('tbody')).toHaveLength(3);

    // 도큐먼트 행은 채널 행보다 들여쓰여 있다
    const channelName = canvas.getAllByText(/^채널명/)[0];
    const documentName = canvas.getAllByText(/^도큐먼트 스페이스명/)[0];
    const channelLeft = channelName.getBoundingClientRect().left;
    const documentLeft = documentName.getBoundingClientRect().left;
    await expect(documentLeft).toBeGreaterThan(channelLeft);

    // 계층이 생겨도 날짜는 여전히 한 줄이어야 한다
    for (const row of rows.slice(1)) {
      await expect(row.getBoundingClientRect().height).toBeLessThanOrEqual(48);
    }
  },
};

/**
 * Figma 716의 절반도 안 되는 슬롯. 대상 열이 줄어들며 truncate 되고,
 * 날짜는 끝까지 한 줄이며, 표가 슬롯 밖으로 넘치지 않아야 한다.
 */
export const Narrow: Story = {
  args: { service: 'channel_talk', rows: ROWS.slice(0, 2) },
  render: (args) => (
    <div className="bg-fill-normal-normal w-80 p-3">
      <EmbeddedResourceTable {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const table = canvas.getByRole('table');
    const slot = table.parentElement as HTMLElement;

    // 가로 넘침 없음 — overflow-x-auto 없이도 슬롯 안에 들어와야 한다.
    // 1px 여유는 열 폭 소수점이 scrollWidth 반올림에서 합쳐진 값이다(실제 넘침 아님)
    await expect(table.getBoundingClientRect().width).toBeLessThanOrEqual(slot.clientWidth);
    await expect(slot.scrollWidth).toBeLessThanOrEqual(slot.clientWidth + 1);

    // 헤더 라벨이 두 줄로 접히면 36을 넘는다
    await expect(canvas.getAllByRole('row')[0].getBoundingClientRect().height).toBe(36);

    // 날짜는 여전히 한 줄 → 행 높이가 안 늘어난다
    for (const row of canvas.getAllByRole('row').slice(1)) {
      await expect(row.getBoundingClientRect().height).toBeLessThanOrEqual(48);
    }

    // 대상 이름은 잘려서 표시된다
    const name = canvas.getAllByText(/^채널명/)[0];
    await expect(name.scrollWidth).toBeGreaterThan(name.clientWidth);
  },
};

export const LongName: Story = {
  args: {
    service: 'confluence',
    label: '임베딩된 스페이스',
    rows: [{ id: 'x', name: '아주 긴 스페이스 이름이 들어가는 경우의 말줄임 확인용 텍스트입니다', dataRange: '-' }],
  },
  render: (args) => (
    <Frame>
      <EmbeddedResourceTable {...args} />
    </Frame>
  ),
};
