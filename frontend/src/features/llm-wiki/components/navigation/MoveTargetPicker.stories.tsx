import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, waitFor, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import MoveTargetPicker, { MOVE_PICKER_FOLDER_INPUT_ATTR, type MoveTargetChannel } from './MoveTargetPicker';

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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18957-54370',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18957:54370',
      },
      viewport: { width: 360, height: 440 },
      states: [
        'expanded',
        'collapsed',
        'searching',
        'current-location',
        'no-folders',
        'create-folder',
        'create-folder-failure',
        'max-height-scroll',
      ],
      reuseNotes: [
        '트리 행이 NavTree와 닮았지만 캐럿이 늘 보이고 행 액션·선택 상태가 없어 재사용하지 않는다.',
        '팝오버 배치·열고 닫기는 소비처(WikiSideNav) 몫이다. 이 컴포넌트는 패널 본문만 낸다.',
        '새 폴더 입력을 SnbRenamePopover로 띄우지 않는 이유: 패널 자체가 팝오버 안이라 중첩 팝오버는 바깥이 outside-interaction으로 닫힌다. 키 관례(Enter 제출·Escape 취소·조합 가드)만 가져왔다.',
      ],
      layoutNotes: [
        '확정 노드 18957:54370 실측(8/24): 패널 폭 300, padding 10/0/0, gap 12, radius 12, Shadow/Modal. 높이는 시안 380을 max-height로만 쓴다 — 고정 높이는 사용자 지시(8/24)로 제거, 내용이 적으면 줄고 넘치면 목록만 스크롤.',
        '검색 구역 padding 0/10, 입력 h36 padding 6/10 gap 8 radius 8. 트리 구역 padding 0/6, 행 간격 2.',
        '채널·폴더 행 모두 h36 padding 6/10 gap 12 — 폴더 들여쓰기는 패딩이 아니라 앞 점 슬롯(22)이 만든다. 구 노드(18849:138185)의 좌측 20 들여쓰기는 폐기.',
        '하단 새 폴더 행: padding 10, gap 12, 상단 보더 #EAEBEC, add 아이콘 20(슬롯 22) + 문구 #6D7882.',
      ],
      dataNotes: [
        '시안은 전 채널 트리였으나 이동 API(PATCH /wiki/artifacts)가 같은 채널 안만 받아 대상을 채널 하나로 좁혔다.',
        '열릴 때는 트리 전체가 펼쳐져 있다(사용자 확정, 8/24). 빈 목록·검색 결과 없음 문구는 시안에 없어 만들지 않는다.',
        '새 폴더 진입점은 확정 노드의 하단 행이다. 이름 입력 UX(같은 자리 인라인 전환·Enter 제출·Escape 취소·빈 값 무시)는 시안에 없어 자작이고, 필드 규격은 위 검색 입력과 같은 토큰이다.',
        '새 폴더는 onCreateFolder가 있어야(=폴더 생성 권한) 선다 — 생성 요청·트리 갱신은 소비처(WikiSideNavContainer) 몫이고, 생성 후 자동 이동은 하지 않는다(사용자 지시 8/24) — 이동은 사용자가 목록에서 직접 고른다.',
        '새 폴더 제출은 onCreateFolder가 resolve해야 닫힌다. 대기 중엔 입력이 잠기고, reject(이름 중복 409 등)면 값을 유지한 채 열어 둔다 — 오류 토스트는 소비처 뮤테이션 몫이다.',
        '이 스토리는 팝오버 없는 bare 렌더라 Escape가 패널 dismiss를 막는지는 못 잰다 — 컨테이너의 onEscapeKeyDown 가드가 참조하는 입력 표식 속성만 계약으로 고정한다.',
      ],
      interactionNotes: [
        '행을 고르면 그 자리를 알리기만 한다 — 이동 요청·토스트는 소비처가 보낸다.',
        '행 전체가 클릭 대상이다 — 라벨 버튼이 아니라 오버레이 버튼이고 캐럿만 그 위에 뜬다(앞 슬롯 죽은 클릭 영역 결함 수정, 8/24).',
        '채널 행 선택이 곧 채널 루트로 꺼내기(folderId null)다 — 시안에 전용 항목이 없어 트리 구조를 그대로 쓴다.',
        '현재 위치 행(폴더 또는 채널 루트)은 비활성이다 — 제자리 이동 요청을 만들지 않는다.',
        '검색 중에는 걸린 폴더가 보여야 하므로 접혀 있어도 펼친다.',
        '폴더가 없는 채널에는 캐럿을 그리지 않고 슬롯만 비워 라벨 정렬을 지킨다.',
        '새 폴더 입력의 Escape는 인라인 입력만 닫는다 — Radix Escape 리스너가 capture 단계라 stopPropagation으로는 못 끊고, 소비처 팝오버의 onEscapeKeyDown이 입력 표식 속성을 보고 dismiss를 preventDefault로 막는다.',
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

    // 고정 높이는 없다 — max-height 계약만 있고 내용이 적으면 패널이 줄어든다.
    await expect(panel.getBoundingClientRect().width).toBe(300);
    await expect(getComputedStyle(panel).maxHeight).toBe('380px');
    await expect(panel.getBoundingClientRect().height).toBeLessThan(380);

    // 새 폴더 푸터가 없는 경로는 하단 패딩이 그 여백을 대신 만든다 — 마지막 행이 테두리에 붙지 않는다.
    await expect(getComputedStyle(panel).paddingBottom).toBe('10px');

    // 열릴 때 트리가 전부 펼쳐져 있다 — 채널 1행 + 폴더 2행.
    const rows = canvas.getAllByTestId('move-target-row');
    await expect(rows).toHaveLength(3);
    await expect(rows[0].getBoundingClientRect().height).toBe(36);

    // 채널·폴더 행은 같은 패딩이다 — 들여쓰기는 폴더 행의 앞 점 슬롯이 만든다
    const box = (element: Element) => element.getBoundingClientRect();
    await expect(box(rows[1]).width).toBe(box(rows[0]).width);
    await expect(Math.round(box(rows[1]).top - box(rows[0]).bottom)).toBe(2);
    await expect(getComputedStyle(rows[1]).paddingLeft).toBe('10px');
    await expect(getComputedStyle(rows[0]).paddingLeft).toBe('10px');

    await userEvent.click(canvas.getByRole('button', { name: '장애 대응' }));
    await expect(onSelect).toHaveBeenCalledWith({
      channelId: 'channel-1',
      folderId: 'folder-2',
      label: '장애 대응',
    });

    // 행 전체가 클릭 대상이다 — 선택 버튼이 행을 그대로 덮는다(앞 슬롯 죽은 영역 없음).
    const folderRow = rows[1];
    const overlay = within(folderRow).getByRole('button', { name: CHANNEL.folders[0].label });
    await expect(box(overlay).left).toBe(box(folderRow).left);
    await expect(box(overlay).width).toBe(box(folderRow).width);
    await expect(box(overlay).height).toBe(box(folderRow).height);

    // 생성 콜백이 없으면 새 폴더 진입점도 없다.
    await expect(canvas.queryByText('새 폴더')).toBeNull();
  },
};

/** 새 폴더 — 하단 진입점을 누르면 같은 자리가 이름 입력으로 바뀐다(입력 UX는 자작). */
export const CreateFolder: Story = {
  args: { channel: CHANNEL, onSelect, onCreateFolder: fn() },
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    // 푸터가 서는 경로는 하단 여백을 푸터가 만든다 — 루트 패딩은 위쪽만 남는다.
    await expect(getComputedStyle(canvas.getByTestId('move-target-picker')).paddingBottom).toBe('0px');

    await userEvent.click(canvas.getByRole('button', { name: '새 폴더' }));
    const input = canvas.getByRole('textbox', { name: '폴더 이름' });
    await expect(input).toHaveFocus();

    // 컨테이너의 Escape dismiss 가드가 이 표식으로 입력을 판별한다.
    await expect(input).toHaveAttribute(MOVE_PICKER_FOLDER_INPUT_ATTR);

    // 빈 값 Enter는 제출로 세지 않는다.
    await userEvent.keyboard('{Enter}');
    await expect(args.onCreateFolder).not.toHaveBeenCalled();

    await userEvent.type(input, '  신규 폴더  ');
    await userEvent.keyboard('{Enter}');
    await expect(args.onCreateFolder).toHaveBeenCalledWith('신규 폴더');

    // 제출이 resolve되면 입력이 닫히고 진입점 행으로 돌아온다.
    await waitFor(() => expect(canvas.queryByRole('textbox', { name: '폴더 이름' })).toBeNull());
    await expect(canvas.getByRole('button', { name: '새 폴더' })).toBeInTheDocument();

    // Escape는 입력만 닫는다 — 취소이므로 콜백이 나가지 않는다.
    await userEvent.click(canvas.getByRole('button', { name: '새 폴더' }));
    await userEvent.keyboard('{Escape}');
    await expect(canvas.queryByRole('textbox', { name: '폴더 이름' })).toBeNull();
    await expect(args.onCreateFolder).toHaveBeenCalledTimes(1);
  },
};

/** 제출 실패(이름 중복 409 등) — 입력을 잃지 않는다. resolve 전에는 잠기고, reject면 값째 열려 있다. */
export const CreateFolderSubmitFailure: Story = {
  args: { channel: CHANNEL, onSelect, onCreateFolder: fn() },
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const onCreateFolder = args.onCreateFolder as ReturnType<typeof fn<(name: string) => Promise<void>>>;

    let rejectCreate!: (reason: Error) => void;
    onCreateFolder.mockImplementationOnce(
      () =>
        new Promise<void>((_, reject) => {
          rejectCreate = reject;
        }),
    );

    await userEvent.click(canvas.getByRole('button', { name: '새 폴더' }));
    const input = canvas.getByRole('textbox', { name: '폴더 이름' });
    await userEvent.type(input, '중복 폴더');
    await userEvent.keyboard('{Enter}');

    // 서버 응답을 기다리는 동안 재제출·수정이 잠긴다.
    await expect(input).toBeDisabled();

    rejectCreate(new Error('FOLDER_NAME_TAKEN'));

    // 실패하면 값을 유지한 채 다시 편집 상태다 — 처음부터 다시 치지 않는다.
    await waitFor(() => expect(input).toBeEnabled());
    await expect(input).toHaveValue('중복 폴더');
    await waitFor(() => expect(input).toHaveFocus());

    // 같은 값으로 재제출이 성공하면 그때 닫힌다.
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(canvas.queryByRole('textbox', { name: '폴더 이름' })).toBeNull());
    await expect(onCreateFolder).toHaveBeenCalledTimes(2);
  },
};

/** 폴더가 많으면 max-height에서 멈추고 목록만 스크롤한다. */
export const MaxHeightScroll: Story = {
  args: {
    channel: {
      id: 'channel-1',
      label: '폴더 많은 채널',
      folders: Array.from({ length: 20 }, (_, index) => ({ id: `folder-${index}`, label: `폴더 ${index + 1}` })),
    },
    onSelect,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const panel = canvas.getByTestId('move-target-picker');

    await expect(panel.getBoundingClientRect().height).toBe(380);

    // 넘친 만큼은 패널이 아니라 목록이 스크롤로 삼킨다.
    const list = panel.querySelector('ul') as HTMLElement;
    await expect(list.scrollHeight).toBeGreaterThan(list.clientHeight);
    await expect(panel.scrollHeight).toBe(panel.clientHeight);
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
