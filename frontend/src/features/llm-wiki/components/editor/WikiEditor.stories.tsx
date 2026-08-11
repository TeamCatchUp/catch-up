import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { EDITOR_PHASE2_DOC, EDITOR_SKELETON_DOC } from '../../fixtures/llmWikiEditorFixtures';
import WikiEditor from './WikiEditor';

/**
 * WikiEditor 스토리. Figma 시안이 없어 모든 스토리가 designSource: 'dev-preview'다.
 * IME 조합 중 동작(Enter·↑↓·Esc)은 자동화 불가 — isComposing 가드·slashCommand 브리지 수정 시 실기기 한글 입력 재검증 필요.
 */
const meta = {
  title: 'Compositions/LLM Wiki/Editor/WikiEditor',
  component: WikiEditor,
  argTypes: {
    // 객체 arg는 Controls가 라이브 JSON 트리로 렌더한다 — 편집 대상이 아니므로 끈다.
    initialContent: { control: false },
    onUpdate: { control: false },
    onContentError: { control: false },
  },
  parameters: {
    // onUpdate가 키 입력마다 문서 전체 JSON을 넘겨 Actions 패널에 쌓인다 — 끈다.
    actions: { disable: true },
    // 회귀 테스트 스토리의 play는 캡처 환경에서 시간이 초과된다 — Playground 3종만 아래에서 다시 켠다.
    chromatic: { disableSnapshot: true },
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      viewport: { width: 720, height: 480 },
      states: [
        'empty',
        'slash-menu-open',
        'slash-after-word',
        'phase2-blocks',
        'callout',
        'drag-handle',
        'with-content',
        'read-only',
        'markdown-shortcut',
        'invalid-content',
        'formatting-toolbar',
        'turn-into',
        'add-block-button',
        'phase2-content',
        'emoji-picker',
      ],
      dataNotes: [
        '저장·API가 없다. 상태는 Tiptap 내부(ProseMirror state)에 있고 onUpdate로 관찰만 한다.',
        'blocks[] 어댑터는 이번 범위 밖이다 — initialContent는 Tiptap JSON 그대로다.',
      ],
      interactionNotes: [
        'uncontrolled다. initialContent는 최초 1회만 반영된다 — 매 키 입력마다 덮어쓰면 커서가 맨 앞으로 튄다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiEditor>;

export default meta;
type Story = StoryObj<typeof WikiEditor>;

/** 손으로 만지는 스토리(play 없음). 사이드바에는 아래 3개만 보인다. */

/** 빈 에디터. `/`로 블록 삽입, 텍스트 선택 시 서식 툴바, `:`로 이모지. */
export const Playground: Story = {
  parameters: { chromatic: { disableSnapshot: false } },
};

/** 문서가 들어 있는 상태. 제목·문단·목록. */
export const PlaygroundWithContent: Story = {
  args: { initialContent: EDITOR_SKELETON_DOC },
  parameters: { chromatic: { disableSnapshot: false } },
};

/** 2차 블록(체크박스·콜아웃·표)이 들어 있는 상태. */
export const PlaygroundWithBlocks: Story = {
  args: { initialContent: EDITOR_PHASE2_DOC },
  parameters: { chromatic: { disableSnapshot: false } },
};

/**
 * 아래는 전부 회귀 테스트용. 에디터 인스턴스가 무거워 autodocs를 쓰지 않고,
 * play가 UI 계측 환경에서 초 단위로 걸려 tags: ['!dev']로 감춘다 — 커버리지는 vitest가 담당한다.
 */

/** 빈 문서. 클릭해서 타이핑하면 글자가 들어간다. */
export const Empty: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const surface = canvas.getByRole('textbox');
    await expect(surface).toBeInTheDocument();

    await userEvent.click(surface);
    await userEvent.keyboard('결제 실패가 증가했다.');

    await expect(surface).toHaveTextContent('결제 실패가 증가했다.');
  },
};

/** /를 치면 메뉴가 뜨고, 항목을 고르면 블록이 바뀐다. */
export const SlashMenuInsert: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const surface = canvas.getByRole('textbox');
    await userEvent.click(surface);
    await userEvent.keyboard('/');

    // 메뉴는 포털로 렌더된다 — body 스코프에서 찾는다.
    await expect(await body.findByText('제목 1')).toBeInTheDocument();

    await userEvent.click(body.getByText('제목 1'));

    // 슬래시 문자는 지워지고 문단이 제목으로 바뀐다.
    await expect(surface.querySelector('h1')).not.toBeNull();
    await expect(surface).not.toHaveTextContent('/');
  },
};

/**
 * 키보드로 항목을 고른다 — ↓로 하이라이트를 옮기고 Enter로 삽입.
 * slashCommand → WikiEditor → SlashMenu로 이어지는 키 이벤트 배선의 회귀 감시.
 */
export const SlashMenuKeyboard: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const surface = canvas.getByRole('textbox');
    await userEvent.click(surface);
    await userEvent.keyboard('/');

    await expect(await body.findByText('제목 1')).toBeInTheDocument();

    // 하이라이트 초기값은 0(제목 1). ↓ 한 번이면 제목 2다.
    await userEvent.keyboard('{ArrowDown}{Enter}');

    await expect(surface.querySelector('h2')).not.toBeNull();
    await expect(surface).not.toHaveTextContent('/');
  },
};

/** 단어 끝에 바로 /를 쳐도 메뉴가 열린다. */
export const SlashAfterWordOpens: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const surface = canvas.getByRole('textbox');
    await userEvent.click(surface);
    await userEvent.keyboard('and/');

    await expect(await body.findByText('제목 1')).toBeInTheDocument();
  },
};

/** 슬래시로 2차 블록 3종(체크박스·표·콜아웃)이 실제로 삽입된다. */
export const SlashInsertsPhase2Blocks: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    await userEvent.click(surface);
    await userEvent.keyboard('/체크');
    await userEvent.click(await body.findByText('체크박스'));
    await expect(surface.querySelector('ul[data-type="taskList"] input[type="checkbox"]')).not.toBeNull();

    // 체크박스 목록을 빠져나와 새 문단에서 표 삽입
    await userEvent.keyboard('{Enter}{Enter}/표');
    await userEvent.click(await body.findByText('표'));
    await expect(surface.querySelectorAll('table td, table th').length).toBeGreaterThan(0);
  },
};

/** 플로팅 서식 툴바 — 텍스트를 선택하면 뜨고, 굵게·정렬이 적용된다. */
export const FormattingToolbarStory: Story = {
  tags: ['!dev'],
  name: 'Formatting Toolbar',
  args: { initialContent: EDITOR_SKELETON_DOC },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    // 선택 전에는 툴바가 없다
    await expect(body.queryByRole('toolbar', { name: '텍스트 서식' })).toBeNull();

    // 헤드리스에서는 tripleClick·{Home}/{End}가 contenteditable 선택을 만들지 못한다.
    // DOM Range를 직접 걸면 selectionchange가 발사되고 ProseMirror가 그걸 집는다.
    const paragraph = within(surface).getByText('검토자 메모: 원인 확인 중.');
    await userEvent.click(paragraph);
    const doc = paragraph.ownerDocument;
    const range = doc.createRange();
    range.selectNodeContents(paragraph);
    const selection = doc.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);

    const toolbar = await body.findByRole('toolbar', { name: '텍스트 서식' });
    await userEvent.click(within(toolbar).getByRole('button', { name: '굵게' }));
    // 마크 적용이 노드 DOM을 재생성할 수 있어 surface에서 재조회한다
    const strong = surface.querySelector('strong');
    await expect(strong).not.toBeNull();
    await expect(strong).toHaveTextContent('검토자 메모');

    // 정렬 — 가운데를 누르면 블록에 text-align이 붙는다
    await userEvent.click(within(toolbar).getByRole('button', { name: '가운데 정렬' }));
    const aligned = surface.querySelector('p[style*="text-align: center"], p[style*="text-align:center"]');
    await expect(aligned).not.toBeNull();
  },
};

/** 블록 전환(turn-into) — 툴바 좌측 드롭다운으로 본문을 제목 2로 바꾼다. */
export const TurnInto: Story = {
  tags: ['!dev'],
  args: { initialContent: EDITOR_SKELETON_DOC },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    const paragraph = within(surface).getByText('검토자 메모: 원인 확인 중.');
    await userEvent.click(paragraph);
    const doc = paragraph.ownerDocument;
    const range = doc.createRange();
    range.selectNodeContents(paragraph);
    const selection = doc.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);

    const toolbar = await body.findByRole('toolbar', { name: '텍스트 서식' });
    await userEvent.click(within(toolbar).getByRole('button', { name: '블록 전환' }));
    await userEvent.click(await body.findByText('제목 2'));

    const h2s = [...surface.querySelectorAll('h2')].map((el) => el.textContent);
    await expect(h2s).toContain('검토자 메모: 원인 확인 중.');
  },
};

/** 드래그 핸들 옆 + 버튼 — 아래에 빈 문단을 만들고 슬래시 메뉴를 연다. */
export const AddBlockButton: Story = {
  tags: ['!dev'],
  args: {
    initialContent: {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: '기준 블록' }] }],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    // 헤드리스에서는 hover가 DragHandle 추적으로 이어지지 않아 + 버튼이 "선택 블록 뒤 삽입" 폴백을 탄다.
    await userEvent.click(within(surface).getByText('기준 블록'));

    // 핸들은 호버 전까지 visibility:hidden이고 user-event는 숨은 요소 클릭을 무시한다 — 네이티브 클릭을 쓴다.
    const addButton = await canvas.findByRole('button', { name: '아래에 블록 추가' });
    (addButton as HTMLButtonElement).click();

    // 슬래시 메뉴가 열린다 — '/' 삽입이 Suggestion을 트리거했다는 뜻
    await expect(await body.findByText('제목 1')).toBeInTheDocument();
  },
};

/** 콜아웃 — 커스텀 노드가 블록을 감싸고 다시 풀 수 있다. */
export const CalloutToggle: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    await userEvent.click(surface);
    await userEvent.keyboard('강조할 내용');
    await userEvent.keyboard('/콜아웃');
    await userEvent.click(await body.findByText('콜아웃'));

    const callout = surface.querySelector('div[data-type="callout"]');
    await expect(callout).not.toBeNull();
    await expect(callout).toHaveTextContent('강조할 내용');
  },
};

/** 드래그 핸들 — 에디터에 호버하면 노출된다. */
export const DragHandle: Story = {
  tags: ['!dev'],
  args: {
    initialContent: {
      type: 'doc',
      content: [
        { type: 'paragraph', content: [{ type: 'text', text: '첫 번째 문단' }] },
        { type: 'paragraph', content: [{ type: 'text', text: '두 번째 문단' }] },
      ],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const surface = canvas.getByRole('textbox');
    await userEvent.hover(surface);

    await expect(canvas.getByTestId('block-drag-handle')).toBeInTheDocument();
  },
};

/** 픽스처 로드. 골격 블록(제목·문단·목록)만 들어 있다. */
export const WithContent: Story = {
  tags: ['!dev'],
  args: { initialContent: EDITOR_SKELETON_DOC, onUpdate: fn() },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const surface = canvas.getByRole('textbox');

    await expect(surface).toHaveTextContent('8월 들어 결제 실패가 증가했다.');
    await expect(surface.querySelector('h2')).not.toBeNull();
    await expect(surface.querySelectorAll('li')).toHaveLength(2);

    // origin·claimIds는 화면에 나오면 안 된다 — 렌더용 값이 아니다.
    await expect(surface.innerHTML).not.toContain('claimIds');
    await expect(surface.innerHTML).not.toContain('c_1');

    // 마운트만으로 onUpdate가 불리면 부모의 dirty 추적이 즉시 "변경됨"이 된다.
    await expect(args.onUpdate).not.toHaveBeenCalled();
  },
};

/** 2차 블록 JSON 로드 — 체크박스·콜아웃·표가 렌더된다. */
export const WithPhase2Content: Story = {
  tags: ['!dev'],
  args: { initialContent: EDITOR_PHASE2_DOC, onContentError: fn() },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const surface = canvas.getByRole('textbox');

    await expect(surface.querySelectorAll('ul[data-type="taskList"] input[type="checkbox"]')).toHaveLength(2);
    await expect(surface.querySelector('ul[data-type="taskList"] input[type="checkbox"]:checked')).not.toBeNull();
    await expect(surface.querySelector('div[data-type="callout"]')).toHaveTextContent('새벽 배치 기준');
    await expect(surface.querySelectorAll('table th')).toHaveLength(2);
    // 스키마 밖 노드가 하나라도 있으면 조용히 소실된다
    await expect(args.onContentError).not.toHaveBeenCalled();
  },
};

/** `:` 이모지 서제스천 — :sm 검색 → 선택 → 이모지 문자 삽입. */
export const EmojiPicker: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    await userEvent.click(surface);
    await userEvent.keyboard(':smile');

    const option = await body.findByText(':smile:');
    await userEvent.click(option);

    await expect(surface.textContent).toContain('😄');
  },
};

/** 읽기 전용. 타이핑해도 내용이 바뀌지 않는다. */
export const ReadOnly: Story = {
  tags: ['!dev'],
  args: { initialContent: EDITOR_SKELETON_DOC, editable: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const surface = canvas.getByRole('textbox');

    const before = surface.textContent;
    await userEvent.click(surface);
    await userEvent.keyboard('이 글자는 들어가면 안 된다');

    await expect(surface.textContent).toBe(before);
  },
};

/**
 * 마크다운 단축 입력(제목·목록·코드). StarterKit의 input rule이라 구현 코드는 없지만,
 * StarterKit 옵션을 건드리면 조용히 깨지므로 여기서 감시한다.
 */
export const MarkdownShortcuts: Story = {
  tags: ['!dev'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const surface = canvas.getByRole('textbox');

    await userEvent.click(surface);

    await userEvent.keyboard('# 제목이 된다{Enter}');
    await expect(surface.querySelector('h1')).not.toBeNull();

    await userEvent.keyboard('- 목록이 된다{Enter}{Enter}');
    await expect(surface.querySelector('ul li')).not.toBeNull();

    // codeBlock input rule은 백틱 3개 "뒤의 공백"이 방아쇠다.
    await userEvent.keyboard('``` ');
    await expect(surface.querySelector('pre code')).not.toBeNull();
  },
};

/**
 * 스키마에 없는 노드가 들어오면 onContentError가 불린다.
 * enableContentCheck를 끄면 ProseMirror가 말없이 버려서 소실이 드러나지 않는다.
 */
export const InvalidContentIsReported: Story = {
  tags: ['!dev'],
  args: {
    onContentError: fn(),
    initialContent: {
      type: 'doc',
      content: [{ type: 'image', attrs: { src: 'x.png' } }],
    },
  },
  play: async ({ args }) => {
    await expect(args.onContentError).toHaveBeenCalled();
  },
};
