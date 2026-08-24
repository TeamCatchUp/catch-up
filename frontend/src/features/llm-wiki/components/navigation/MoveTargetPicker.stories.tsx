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
      states: ['expanded', 'collapsed', 'searching', 'current-location', 'no-folders'],
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
        '시안은 전 채널 트리였으나 이동 API(PATCH /wiki/artifacts)가 같은 채널 안만 받아 대상을 채널 하나로 좁혔다.',
        '채널이 하나뿐이라 처음부터 펼쳐 폴더가 바로 보인다. 빈 목록·검색 결과 없음 문구는 시안에 없어 만들지 않는다.',
      ],
      interactionNotes: [
        '행을 고르면 그 자리를 알리기만 한다 — 이동 요청·토스트는 소비처가 보낸다.',
        '채널 행 선택이 곧 채널 루트로 꺼내기(folderId null)다 — 시안에 전용 항목이 없어 트리 구조를 그대로 쓴다.',
        '현재 위치 행(폴더 또는 채널 루트)은 비활성이다 — 제자리 이동 요청을 만들지 않는다.',
        '검색 중에는 걸린 폴더가 보여야 하므로 접혀 있어도 펼친다.',
        '폴더가 없는 채널에는 캐럿을 그리지 않고 슬롯만 비워 라벨 정렬을 지킨다.',
      ],
      tokenNotes: [
        '패널 테두리 #e1e2e4=line/normal/normal, 검색 테두리 #eaebec=line/normal/neutral.',
        '폴더 앞 점은 보더 1.5px #cdd1d5=icon/normal/assistive로 NavTree depth2 점과 같은 토큰이다.',
        'hover는 행 bg 6%(fill interaction hover), 캐럿 버튼 10%(pressed)로 시안 알파와 같다.',
        '비활성 행 라벨은 text/normal/assistive — 비활성 시안이 없어 버튼 disabled 관례를 따른다.',
      ],
    }),
  },
} satisfies Meta<typeof MoveTargetPicker>;

export default meta;

type Story = StoryObj<typeof MoveTargetPicker>;

const CHANNEL: MoveTargetChannel = {
  id: 'channel-1',
  label: '채널명 text text text text text text text text',
  folders: [
    { id: 'folder-1', label: '폴더명 text text text text text text text' },
    { id: 'folder-2', label: '장애 대응' },
  ],
};

const onSelect = fn();

export const Expanded: Story = {
  args: { channel: CHANNEL, onSelect },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const panel = canvas.getByTestId('move-target-picker');

    // 시안 실측 300×380
    await expect(panel.getBoundingClientRect().width).toBe(300);
    await expect(panel.getBoundingClientRect().height).toBe(380);

    // 채널 하나가 처음부터 펼쳐져 채널 1행 + 폴더 2행이 선다
    const rows = canvas.getAllByTestId('move-target-row');
    await expect(rows).toHaveLength(3);
    await expect(rows[0].getBoundingClientRect().height).toBe(36);

    // 행 배경은 같은 폭이고 폴더만 좌측으로 10 더 들어간다 (padding 10 → 20)
    const box = (element: Element) => element.getBoundingClientRect();
    await expect(box(rows[1]).width).toBe(box(rows[0]).width);
    await expect(Math.round(box(rows[1]).top - box(rows[0]).bottom)).toBe(2);
    await expect(getComputedStyle(rows[1]).paddingLeft).toBe('20px');
    await expect(getComputedStyle(rows[0]).paddingLeft).toBe('10px');

    await userEvent.click(canvas.getByRole('button', { name: '장애 대응' }));
    await expect(onSelect).toHaveBeenCalledWith({
      channelId: 'channel-1',
      folderId: 'folder-2',
      label: '장애 대응',
    });
  },
};

export const Collapsed: Story = {
  args: { channel: CHANNEL, onSelect },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: `${CHANNEL.label} 접기` }));

    // 접으면 채널 행만 남는다
    await expect(canvas.getAllByTestId('move-target-row')).toHaveLength(1);
    await expect(canvas.getByRole('button', { name: `${CHANNEL.label} 펼치기` })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  },
};

/** 채널 행 선택이 곧 채널 루트(folderId null)로 꺼내기다 */
export const RootMove: Story = {
  args: { channel: CHANNEL, currentFolderId: 'folder-1', onSelect },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: CHANNEL.label }));
    await expect(onSelect).toHaveBeenCalledWith({
      channelId: 'channel-1',
      folderId: null,
      label: CHANNEL.label,
    });
  },
};

/** 현재 위치 행은 비활성이다 — 폴더에 있으면 그 폴더가, 루트에 있으면 채널 행이 잠긴다 */
export const CurrentLocation: Story = {
  args: { channel: CHANNEL, currentFolderId: 'folder-2', onSelect },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: '장애 대응' })).toBeDisabled();
    await expect(canvas.getByRole('button', { name: CHANNEL.label })).toBeEnabled();
  },
};

export const CurrentLocationRoot: Story = {
  args: { channel: CHANNEL, currentFolderId: null, onSelect },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: CHANNEL.label })).toBeDisabled();
    await expect(canvas.getByRole('button', { name: '장애 대응' })).toBeEnabled();
  },
};

/** 검색은 그 채널의 폴더 안에서만 훑고, 접혀 있어도 걸린 폴더가 보이게 펼친다 */
export const Searching: Story = {
  args: { channel: CHANNEL, onSelect },
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: `${CHANNEL.label} 접기` }));
    await userEvent.type(canvas.getByRole('textbox', { name: '파일 옮길 곳 선택' }), '장애');

    // 걸린 폴더 한 줄과 채널 머리 행만 남는다
    await expect(canvas.getAllByTestId('move-target-row')).toHaveLength(2);
    await expect(canvas.getByRole('button', { name: '장애 대응' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: CHANNEL.folders[0].label })).toBeNull();
  },
};

export const NoFolders: Story = {
  args: { channel: { id: 'channel-2', label: '폴더 없는 채널', folders: [] }, onSelect },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 폴더가 없으면 캐럿을 만들지 않고 채널 행만 선다
    await expect(canvas.getAllByTestId('move-target-row')).toHaveLength(1);
    await expect(canvas.queryByRole('button', { name: '폴더 없는 채널 펼치기' })).toBeNull();
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
