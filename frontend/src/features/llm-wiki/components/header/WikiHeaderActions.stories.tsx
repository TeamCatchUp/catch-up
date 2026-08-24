import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import WikiHeaderActions from './WikiHeaderActions';

const onCopyLink = fn();
const onRenameSubmit = fn();

const body = (canvasElement: HTMLElement) => within(canvasElement.ownerDocument.body);
const radius = (element: Element) => parseFloat(getComputedStyle(element).borderTopLeftRadius);

const meta = {
  title: 'Compositions/LLM Wiki/Header/WikiHeaderActions',
  component: WikiHeaderActions,
  tags: ['autodocs'],
  args: {
    kind: 'channel',
    name: '채널명',
    onCopyLink,
    onRenameSubmit,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18890-93951',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18890:93951',
      },
      viewport: { width: 400, height: 320 },
      states: ['main-channel', 'detail-folder', 'without-rename', 'menu-open', 'rename-open'],
      reuseNotes: [
        '메뉴 껍데기는 SNB 트리 케밥과 같은 SnbDropdownMenu(250w·padding 8/6·radius 12)를 그대로 쓴다 — 시안 18890:93951과 규격이 같아 새로 만들지 않았다.',
        '이름 바꾸기 입력도 SNB의 SnbRenamePopover 재사용이다. 케밥과 같은 팝오버 자리에서 내용만 갈린다.',
        '버튼은 shared Button icon-only-gray다. main=size md(36·radius 8, Icon button 585:5628), detail=size sm + size-7(28·radius full, 585:6791) — 후자는 BlockDiffCard의 같은 조합 선례를 따랐다.',
      ],
      dataNotes: [
        '시안 메뉴의 채널 설정 보기·도움말·버전 기록은 목적지 화면·API가 없어 항목을 만들지 않는다 — 무동작 항목을 두지 않는다.',
        '하단 메타(최종 편집자·시각)는 채널·폴더에 대응 필드가 없어 비운다(artifact 전용). 필드가 오면 metaLines만 채우면 된다.',
        '이름 바꾸기는 채널 관리자에게만 온다 — 콜백이 없으면 남는 항목이 없어 케밥 자체가 서지 않는다.',
        '링크 복사 문구·실패 토스트는 SNB 케밥과 같은 통로를 쓴다. 이 컴포넌트는 클릭만 알린다.',
      ],
      tokenNotes: [
        '카테고리 라벨 "작업 더보기" body(md)/xsmall #6D7882, 항목 라벨 body(md)/small #33363D — SnbDropdownMenu가 이미 그 값이다.',
        '아이콘은 icon/link·icon/kebab__horiz_300·icon/edit_square 기존 자산이다.',
      ],
      layoutNotes: [
        'main 버튼 36×36 radius 8 + 아이콘 24, detail 버튼 28×28 radius full + 아이콘 20 — 시안 17752:45516·17762:104786 실측.',
        '두 버튼 사이 간격은 헤더의 actions 슬롯이 정한다 — 이 컴포넌트는 버튼만 낸다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiHeaderActions>;

export default meta;
type Story = StoryObj<typeof WikiHeaderActions>;

/** 채널 헤더(main) — 36px 사각 버튼 2개. */
export const MainChannel: Story = {
  args: { variant: 'main' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const copy = canvas.getByRole('button', { name: '링크 복사' });
    const more = canvas.getByRole('button', { name: '작업 더보기' });

    for (const button of [copy, more]) {
      await expect(button.getBoundingClientRect().width).toBe(36);
      await expect(button.getBoundingClientRect().height).toBe(36);
      await expect(radius(button)).toBe(8);
      await expect(button.querySelector('svg')!.getBoundingClientRect().width).toBe(24);
    }

    await userEvent.click(copy);
    await expect(onCopyLink).toHaveBeenCalled();
  },
};

/** 폴더 헤더(detail) — 28px 원형 버튼 2개. main과 갈리는 유일한 기하다. */
export const DetailFolder: Story = {
  args: { variant: 'detail', kind: 'folder', name: '폴더명' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    for (const name of ['링크 복사', '작업 더보기']) {
      const button = canvas.getByRole('button', { name });
      await expect(button.getBoundingClientRect().width).toBe(28);
      await expect(button.getBoundingClientRect().height).toBe(28);
      // rounded-full은 계산값이 큰 수라 정확값 대신 반지름 하한으로 잰다
      await expect(radius(button)).toBeGreaterThanOrEqual(14);
      await expect(button.querySelector('svg')!.getBoundingClientRect().width).toBe(20);
    }
  },
};

/** 케밥 메뉴 — 시안 6구역 중 목적지가 있는 항목만 남는다. */
export const MenuOpen: Story = {
  args: { variant: 'main' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const menu = body(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '작업 더보기' }));

    // 팝오버가 열리며 scale이 걸려 있어 getBoundingClientRect가 아니라 레이아웃 폭으로 잰다
    const shell = (await menu.findByTestId('snb-dropdown-menu')) as HTMLElement;
    await expect(shell.offsetWidth).toBe(250);
    await expect(menu.getByText('작업 더보기', { selector: 'span' })).toBeInTheDocument();
    await expect(menu.getByRole('button', { name: '이름 바꾸기' })).toBeInTheDocument();

    // 목적지가 없는 항목과 데이터가 없는 메타는 만들지 않는다 — 무동작 어포던스가 생기면 여기서 잡힌다
    for (const absent of ['채널 설정 보기', '도움말', '버전 기록']) {
      await expect(menu.queryByRole('button', { name: absent })).toBeNull();
    }
    await expect(menu.queryByTestId('snb-dropdown-menu-meta')).toBeNull();
    await expect(menu.queryAllByTestId('snb-dropdown-menu-divider')).toHaveLength(0);
  },
};

/** 이름 바꾸기 — 케밥 자리에서 입력으로 이어진다. */
export const RenameOpen: Story = {
  args: { variant: 'main' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const menu = body(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '작업 더보기' }));
    await userEvent.click(await menu.findByRole('button', { name: '이름 바꾸기' }));

    // 메뉴가 입력으로 교체된다 — 두 개가 함께 뜨면 자리가 겹친다
    await expect(await menu.findByTestId('snb-rename-popover')).toBeInTheDocument();
    await expect(menu.queryByTestId('snb-dropdown-menu')).toBeNull();

    const field = menu.getByRole('textbox', { name: '이름 바꾸기' });
    await expect(field).toHaveValue('채널명');

    await userEvent.clear(field);
    await userEvent.type(field, '새 이름{Enter}');
    await expect(onRenameSubmit).toHaveBeenCalledWith('새 이름');
  },
};

/** 관리자가 아닌 채널 — 남는 항목이 없어 케밥 자체를 만들지 않는다. */
export const WithoutRename: Story = {
  args: { variant: 'main', onRenameSubmit: undefined },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: '링크 복사' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '작업 더보기' })).toBeNull();
  },
};
