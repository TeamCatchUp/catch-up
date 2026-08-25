import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fireEvent, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import SnbRenamePopover from './SnbRenamePopover';

const meta = {
  title: 'Compositions/Shared/Layout/SideNavBar/Parts/SnbRenamePopover',
  component: SnbRenamePopover,
  tags: ['autodocs'],
  args: { kind: 'document' },
  argTypes: {
    kind: { control: 'inline-radio', options: ['channel', 'folder', 'document'] },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'shared',
      fsdLayer: 'shared',
      owner: 'shared',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18658-50794',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18658:50794',
      },
      viewport: { width: 420, height: 320 },
      states: ['channel', 'folder', 'document', 'default', 'focused', 'max-height', 'ime-composing', 'submit-trims'],
      reuseNotes: [
        '채널·폴더·파일 3종은 아이콘만 갈리고 셸·입력 규격이 같다. 그래서 컴포넌트를 나누지 않고 kind prop으로 가른다.',
        '자동 성장은 리포 선례(scrollHeight를 상한으로 클램프)를 그대로 따른다. 새 훅이나 라이브러리를 들이지 않았다.',
        '팝오버 배치·열고 닫기·트리거는 소비처 몫이다. 이 컴포넌트는 입력과 키 처리만 낸다.',
      ],
      layoutNotes: [
        '8/19 시안 재실측: 셸 325w, radius 12, padding 6, gap 6. 아이콘 박스 35×35 radius 8(padding 4, 아이콘 20 중앙). 입력 필드 padding 6/8 radius 8.',
        '시안 프레임명이 max-height 200/201/202로 갈린 세 변형은 같은 상한을 뜻한다 — 상한이 걸리는 대상은 텍스트 영역이고, 그래서 필드는 212, 셸은 224가 된다.',
        'Figma stroke는 레이아웃을 밀지 않아 셸 총높이가 224지만, CSS border 1px이 위아래로 실제 높이를 차지해 브라우저 실측은 2px 크다. SnbDropdownMenu와 같은 처리다.',
        '같은 이유로 입력 폭도 시안 272/텍스트 256에 대해 브라우저는 270/254다. 시안 텍스트 폭에 딱 맞는 이름은 브라우저에서 한 글자 먼저 줄바꿈한다 — 배치 어서션에 짧은 이름을 쓰는 이유다.',
        '입력 필드 테두리는 default 1px → focused 1.5px로 두께가 바뀐다. border로 그리면 상태 전환마다 입력 폭이 0.5px씩 밀려서 ring으로 그렸다(시안 strokeAlign도 OUTSIDE다).',
      ],
      dataNotes: [
        '시안의 입력 문구는 값 텍스트(Text/Normal/Normal)라 placeholder 상태가 아니다. placeholder는 optional prop이고 기본 문구를 정하지 않았다.',
        '에러·글자수 카운터·중복 이름 안내는 시안에 없어 만들지 않았다.',
        '제출값은 trim해서 넘기고 공백뿐인 값은 제출하지 않는다 — 서버 제약이 min_length뿐이라 공백 이름·꼬리 공백이 유사 중복 폴더를 만든다. 옮기기 패널의 새 폴더 입력과 같은 정규화다.',
      ],
      interactionNotes: [
        'Enter 저장 / Escape 취소 / Shift+Enter 줄바꿈은 시안 근거 없는 기본값이다. 시안에 저장·취소 버튼도 트리거 표기도 없다 — 디자이너 확인 필요.',
        '열릴 때 자동 포커스 + 기존 이름 전체 선택도 시안 근거 없는 기본값이다 — 디자이너 확인 필요.',
        'blur 저장은 넣지 않았다. 통상적이긴 하나 시안 근거가 없어 발명하지 않고 onSubmit·onCancel만 노출한다.',
        "aria-label 기본값 '이름 바꾸기'는 이 팝오버를 여는 SnbDropdownMenu 항목 라벨과 시안 섹션명에서 가져왔다.",
        '조합 중 Enter는 isComposing으로 걸러 제출하지 않는다. userEvent로는 조합을 만들 수 없어 keydown을 직접 쏴서 검증한다.',
      ],
      tokenNotes: [
        '아이콘 박스 #F7FBFF = bg-fill-primary-normal-assistive, 아이콘 #3385FF = text-icon-primary-assistive.',
        '입력 테두리 default #EAEBEC = ring-line-normal-neutral, focused #69A5FF = focus-within:ring-line-primary-normal.',
        '셸 테두리는 브리프에 없던 항목이다 — 시안 재실측 결과 Line/Normal/Normal #E1E2E4가 1px 들어간다 = border-line-normal-normal.',
        '본문 body(md)/small 15/1.5/500 #33363D = text-body-small + text-text-normal-normal. 구현 토큰과 값이 일치한다.',
        '그림자는 시안이 0 4px 15px rgba(0,0,0,0.16)인데 리포 토큰 --shadow-dropdown-menu는 0 2px 15px rgba(0,0,0,0.15)다. 값을 박지 않고 토큰을 썼다 — 드리프트는 디자인 시스템 쪽에서 정리할 몫이다.',
      ],
    }),
  },
} satisfies Meta<typeof SnbRenamePopover>;

export default meta;

type Story = StoryObj<typeof SnbRenamePopover>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-100 flex-col items-start p-4">{children}</div>
);

const box = (element: Element) => element.getBoundingClientRect();
const svgOf = (element: Element) => element.querySelector('svg')!;

/** 시안 문구를 그대로 쓴 표본이다 — 실제 이름 규칙이 아니다 */
const SAMPLE_NAME = '내용을 입력해주세요.내용을 입내용을 입력';
const LONG_NAME = SAMPLE_NAME.repeat(12);
/** 같은 시안의 트리 행 라벨. 한 줄에 남아야 하는 배치 검증에 쓴다 */
const SHORT_NAME = '채널명 text text';

const onSubmit = fn();
const onCancel = fn();

export const ChannelRename: Story = {
  args: { kind: 'channel', defaultValue: SHORT_NAME },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const popover = canvas.getByTestId('snb-rename-popover');
    const iconBox = canvas.getByTestId('snb-rename-popover-icon');
    const field = canvas.getByTestId('snb-rename-popover-field');

    // 껍데기 규격
    await expect(box(popover).width).toBe(325);
    await expect(getComputedStyle(popover).borderRadius).toBe('12px');
    await expect(getComputedStyle(popover).borderTopColor).toBe('rgb(225, 226, 228)');
    await expect(popover.clientTop).toBe(1);

    // 아이콘 박스 35×35 radius 8, 아이콘 20
    await expect(box(iconBox).width).toBe(35);
    await expect(box(iconBox).height).toBe(35);
    await expect(getComputedStyle(iconBox).borderRadius).toBe('8px');
    await expect(getComputedStyle(iconBox).backgroundColor).toBe('rgb(247, 251, 255)');
    await expect(box(svgOf(iconBox)).width).toBe(20);
    await expect(getComputedStyle(svgOf(iconBox)).color).toBe('rgb(51, 133, 255)');

    // 채널만 path가 둘이다 — 3종이 실제로 다른 자산을 그리는지 여기서 갈린다
    await expect(svgOf(iconBox).getAttribute('viewBox')).toBe('0 0 24 24');
    await expect(svgOf(iconBox).querySelectorAll('path')).toHaveLength(2);

    // padding 6 / gap 6 — 총높이가 아니라 간격 분배를 고정한다
    const border = popover.clientTop;
    await expect(Math.round(box(iconBox).left - box(popover).left - border)).toBe(6);
    await expect(Math.round(box(iconBox).top - box(popover).top - border)).toBe(6);
    await expect(Math.round(box(field).left - box(iconBox).right)).toBe(6);
    await expect(Math.round(box(popover).right - box(field).right - border)).toBe(6);

    // 열리면 곧바로 편집 상태 — 시안 근거 없는 기본값이다
    const textarea = canvas.getByRole('textbox');
    await expect(document.activeElement).toBe(textarea);
    await expect((textarea as HTMLTextAreaElement).selectionStart).toBe(0);
    await expect((textarea as HTMLTextAreaElement).selectionEnd).toBe(SHORT_NAME.length);
  },
};

export const FolderRename: Story = {
  args: { kind: 'folder', defaultValue: SHORT_NAME },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const icon = svgOf(canvas.getByTestId('snb-rename-popover-icon'));

    await expect(icon.getAttribute('viewBox')).toBe('0 0 24 24');
    await expect(icon.querySelectorAll('path')).toHaveLength(1);
    // 자산이 currentColor여야 토큰 클래스가 먹는다
    await expect(getComputedStyle(icon.querySelector('path')!).fill).toBe('rgb(51, 133, 255)');
  },
};

export const DocumentRename: Story = {
  args: { kind: 'document', defaultValue: SHORT_NAME },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const icon = svgOf(canvas.getByTestId('snb-rename-popover-icon'));

    // 파일 자산만 20 그리드다 — 폴더·채널(24)과 여기서 갈린다
    await expect(icon.getAttribute('viewBox')).toBe('0 0 20 20');
    await expect(box(icon).width).toBe(20);

    // 본문 타이포는 body(md)/small
    const textarea = canvas.getByRole('textbox');
    const style = getComputedStyle(textarea);
    await expect(style.fontSize).toBe('15px');
    await expect(style.fontWeight).toBe('500');
    await expect(style.color).toBe('rgb(51, 54, 61)');
  },
};

/** 포커스가 빠진 상태 — 테두리 색만 갈리고 배치는 그대로여야 한다 */
export const DefaultUnfocused: Story = {
  args: { kind: 'document', defaultValue: SHORT_NAME },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const textarea = canvas.getByRole('textbox') as HTMLTextAreaElement;
    const field = canvas.getByTestId('snb-rename-popover-field');
    const popover = canvas.getByTestId('snb-rename-popover');

    const focusedWidth = box(field).width;
    const focusedShadow = getComputedStyle(field).boxShadow;
    await expect(focusedShadow).toContain('rgb(105, 165, 255)');

    textarea.blur();
    await expect(document.activeElement).not.toBe(textarea);

    const idleShadow = getComputedStyle(field).boxShadow;
    await expect(idleShadow).toContain('rgb(234, 235, 236)');

    // ring이라 두께가 1 → 1.5로 바뀌어도 입력 폭이 밀리지 않는다
    await expect(box(field).width).toBe(focusedWidth);

    // 한 줄 상태의 셸·필드 높이. 시안 47/35에 CSS 테두리 2px가 더 붙는다
    await expect(Math.round(box(field).height)).toBe(35);
    await expect(Math.round(box(popover).height) - 2 * popover.clientTop).toBe(47);
  },
};

/** 내용이 길어지면 세로로 자라다 상한에서 멈추고 스크롤한다 */
export const LongNameCapsAt200: Story = {
  args: { kind: 'channel', defaultValue: LONG_NAME },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const textarea = canvas.getByRole('textbox') as HTMLTextAreaElement;
    const field = canvas.getByTestId('snb-rename-popover-field');
    const popover = canvas.getByTestId('snb-rename-popover');

    // 눈이 아니라 값으로 상한을 고정한다
    await expect(box(textarea).height).toBe(200);
    await expect(textarea.scrollHeight).toBeGreaterThan(200);
    await expect(getComputedStyle(textarea).overflowY).toBe('auto');

    // 상한이 걸리는 대상은 텍스트 영역이다 — 필드·셸은 그 위에 패딩만 얹는다
    await expect(Math.round(box(field).height)).toBe(212);
    await expect(Math.round(box(popover).height) - 2 * popover.clientTop).toBe(224);

    // 아이콘은 위쪽 정렬이 아니라 세로 중앙이다
    const iconBox = canvas.getByTestId('snb-rename-popover-icon');
    const centerGap = box(iconBox).top + box(iconBox).height / 2 - (box(popover).top + box(popover).height / 2);
    await expect(Math.round(centerGap)).toBe(0);
  },
};

/** 짧은 이름은 한 줄에서 시작해 내용만큼만 자란다 */
export const GrowsWhileTyping: Story = {
  args: { kind: 'folder', defaultValue: '' },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const textarea = canvas.getByRole('textbox') as HTMLTextAreaElement;
    const singleLine = box(textarea).height;

    await expect(getComputedStyle(textarea).overflowY).toBe('hidden');

    // Shift+Enter는 줄바꿈이다 — 시안 근거 없는 기본값이다
    await userEvent.type(textarea, 'a{Shift>}{Enter}{/Shift}b');
    await expect(textarea.value).toBe('a\nb');
    await expect(box(textarea).height).toBeGreaterThan(singleLine);
    await expect(box(textarea).height).toBeLessThanOrEqual(200);
  },
};

/** 조합 중 Enter는 한글 확정이라 제출로 세지 않는다 */
export const ComposingEnterIgnored: Story = {
  args: { kind: 'document', defaultValue: '기존 이름', onSubmit, onCancel },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const textarea = canvas.getByRole('textbox') as HTMLTextAreaElement;
    onSubmit.mockClear();
    onCancel.mockClear();

    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });
    await expect(onSubmit).not.toHaveBeenCalled();

    // 조합이 끝난 Enter만 제출로 센다
    fireEvent.keyDown(textarea, { key: 'Enter' });
    await expect(onSubmit).toHaveBeenCalledWith('기존 이름');

    await userEvent.keyboard('{Escape}');
    await expect(onCancel).toHaveBeenCalled();
  },
};

/** 제출 정규화 — 앞뒤 공백은 지우고, 공백뿐인 이름은 제출하지 않는다 */
export const SubmitTrimsName: Story = {
  args: { kind: 'folder', defaultValue: '', onSubmit },
  render: (args) => (
    <Frame>
      <SnbRenamePopover {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const textarea = canvas.getByRole('textbox') as HTMLTextAreaElement;
    onSubmit.mockClear();

    await userEvent.type(textarea, '   ');
    await userEvent.keyboard('{Enter}');
    await expect(onSubmit).not.toHaveBeenCalled();

    await userEvent.clear(textarea);
    await userEvent.type(textarea, '  장애 대응  ');
    await userEvent.keyboard('{Enter}');
    await expect(onSubmit).toHaveBeenCalledWith('장애 대응');
  },
};
