import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import MoveTargetPicker, { type MoveTargetChannel } from './MoveTargetPicker';

const meta = {
  title: 'Compositions/LLM Wiki/Navigation/MoveTargetPicker',
  component: MoveTargetPicker,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18822-137293',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18822:137293',
      },
      viewport: { width: 360, height: 440 },
      states: ['collapsed', 'expanded', 'searching', 'no-folders'],
      reuseNotes: [
        '트리 행이 NavTree와 닮았지만 캐럿이 늘 보이고 행 액션·선택 상태가 없어 재사용하지 않는다.',
        '팝오버 배치·열고 닫기는 소비처(WikiSideNav) 몫이다. 이 컴포넌트는 패널 본문만 낸다.',
      ],
      layoutNotes: [
        '시안 18849:138185 재실측(8/24): 패널 300×380, padding 10/0, gap 12, radius 12, Shadow/Modal.',
        '검색 구역 padding 0/10, 입력 h36 padding 6/10 gap 8 radius 8. 트리 구역 padding 0/6, 행 간격 2.',
        '채널 행 h36 padding 6/10 gap 12, 폴더 행은 좌측만 20으로 들어간다. 앞 슬롯은 22×22 두 칸이다.',
      ],
      dataNotes: [
        '대상 목록은 SNB 트리가 이미 들고 있는 채널·폴더다 — 추가 왕복이 없다.',
        '빈 목록·검색 결과 없음 문구는 시안에 없어 만들지 않는다.',
      ],
      interactionNotes: [
        '행을 고르면 그 자리를 알리기만 한다 — 이동 요청·토스트는 소비처가 보낸다.',
        '검색 중에는 걸린 폴더가 보여야 하므로 접힌 채널도 함께 펼친다.',
        '폴더가 없는 채널에는 캐럿을 그리지 않고 슬롯만 비워 라벨 정렬을 지킨다.',
      ],
      tokenNotes: [
        '패널 테두리 #e1e2e4=line/normal/normal, 검색 테두리 #eaebec=line/normal/neutral.',
        '폴더 앞 점은 보더 1.5px #cdd1d5=icon/normal/assistive로 NavTree depth2 점과 같은 토큰이다.',
        'hover는 행 bg 6%(fill interaction hover), 캐럿 버튼 10%(pressed)로 시안 알파와 같다.',
      ],
    }),
  },
} satisfies Meta<typeof MoveTargetPicker>;

export default meta;

type Story = StoryObj<typeof MoveTargetPicker>;

const CHANNELS: readonly MoveTargetChannel[] = [
  {
    id: 'channel-1',
    label: '채널명 text text text text text text text text',
    folders: [
      { id: 'folder-1', label: '폴더명 text text text text text text text' },
      { id: 'folder-2', label: '장애 대응' },
    ],
  },
  { id: 'channel-2', label: '고객 응대', folders: [{ id: 'folder-3', label: '환불 정책' }] },
  { id: 'channel-3', label: '폴더 없는 채널', folders: [] },
];

const onSelect = fn();

export const Collapsed: Story = {
  args: { channels: CHANNELS, onSelect },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const panel = canvas.getByTestId('move-target-picker');

    // 시안 실측 300×380
    await expect(panel.getBoundingClientRect().width).toBe(300);
    await expect(panel.getBoundingClientRect().height).toBe(380);

    // 접힌 상태에서는 채널 3행만 선다
    const rows = canvas.getAllByTestId('move-target-row');
    await expect(rows).toHaveLength(3);
    await expect(rows[0].getBoundingClientRect().height).toBe(36);

    // 폴더가 없는 채널에는 캐럿을 만들지 않는다
    await expect(canvas.queryByRole('button', { name: '폴더 없는 채널 펼치기' })).toBeNull();
  },
};

export const Expanded: Story = {
  args: { channels: CHANNELS, onSelect },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '고객 응대 펼치기' }));
    const folderRow = canvas.getByRole('button', { name: '환불 정책' }).closest('[data-testid="move-target-row"]')!;
    const channelRow = canvas.getByRole('button', { name: '고객 응대' }).closest('[data-testid="move-target-row"]')!;

    // 행 배경은 같은 폭이고 폴더만 좌측으로 10 더 들어간다 (padding 10 → 20)
    const box = (element: Element) => element.getBoundingClientRect();
    await expect(box(folderRow).width).toBe(box(channelRow).width);
    await expect(Math.round(box(folderRow).top - box(channelRow).bottom)).toBe(2);
    await expect(getComputedStyle(folderRow).paddingLeft).toBe('20px');
    await expect(getComputedStyle(channelRow).paddingLeft).toBe('10px');

    await userEvent.click(canvas.getByRole('button', { name: '환불 정책' }));
    await expect(onSelect).toHaveBeenCalledWith({
      channelId: 'channel-2',
      folderId: 'folder-3',
      label: '환불 정책',
    });
  },
};

/** 검색은 채널·폴더 이름을 함께 훑고, 걸린 폴더가 보이도록 그 채널을 펼친다 */
export const Searching: Story = {
  args: { channels: CHANNELS, onSelect },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.type(canvas.getByRole('textbox', { name: '파일 옮길 곳 선택' }), '환불');

    // 걸린 폴더 한 줄과 그 채널만 남는다
    await expect(canvas.getAllByTestId('move-target-row')).toHaveLength(2);
    await expect(canvas.getByRole('button', { name: '환불 정책' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '장애 대응' })).toBeNull();
  },
};

/** 대상이 아직 없을 때 — 빈 문구를 만들지 않아 검색줄만 남는다 */
export const NoTargets: Story = {
  args: { onSelect },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryAllByTestId('move-target-row')).toHaveLength(0);
    await expect(canvas.getByTestId('move-target-picker').textContent).toBe('');
  },
};
