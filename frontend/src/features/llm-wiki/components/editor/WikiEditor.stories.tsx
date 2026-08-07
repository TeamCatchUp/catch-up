import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { EDITOR_SKELETON_DOC } from '../../fixtures/llmWikiEditorFixtures';
import WikiEditor from './WikiEditor';

/**
 * 이 에디터는 Figma 시안이 없다 — 문서_문서 메인(17735:186169)의 본문이 빈 박스다.
 * 그래서 모든 스토리가 designSource: 'dev-preview'다. figma 키를 넣으면 타입 에러가 난다.
 *
 * ── 한글 IME 수동 체크리스트 (자동 테스트로 못 잡는다) ──────────────
 * □ /로 메뉴 열기 → 한글로 검색 → Enter로 선택
 * □ 조합 중 Enter가 항목을 선택해버리지 않는가
 * □ 조합 중 ↑↓가 커서를 옮기지 않는가
 * □ Esc로 닫은 뒤 조합 중이던 글자가 남는가
 * ────────────────────────────────────────────────────
 * composition 이벤트는 실제 IME 엔진이 있어야 재현된다. Playwright의 insertText로는
 * 조합 과정이 생기지 않아, 가짜 이벤트로 테스트를 만들면 "통과하는데 실제로는 깨지는"
 * 형태가 된다. 스토리를 여는 사람이 검증자다.
 */
const meta = {
  title: 'Compositions/LLM Wiki/Editor/WikiEditor',
  component: WikiEditor,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      viewport: { width: 720, height: 480 },
      states: ['empty', 'slash-menu-open', 'drag-handle', 'with-content', 'read-only', 'markdown-shortcut', 'invalid-content'],
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

/** 빈 문서. 클릭해서 타이핑하면 글자가 들어간다. */
export const Empty: Story = {
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

/** 글 중간의 /는 메뉴를 열지 않는다. and/or 를 칠 때 떠서는 안 된다. */
export const SlashInsideWordDoesNotOpen: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const surface = canvas.getByRole('textbox');
    await userEvent.click(surface);
    await userEvent.keyboard('and/');

    await expect(body.queryByText('제목 1')).toBeNull();
  },
};

/**
 * 드래그 핸들. 명세·Figma 근거가 없는 유일한 기능이라 시각을 최소로 뒀다
 * (drag_indicator.svg + 호버 시 노출). 시안 요청은 design-request에 올라가 있다.
 */
export const DragHandle: Story = {
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

/** 픽스처 로드. 골격 블록만 들어 있다 — 표·체크박스·콜아웃은 다음 단계다. */
export const WithContent: Story = {
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

    // 사용자가 아무것도 치지 않았는데 onUpdate가 불리면 안 된다 — 부모의 dirty 추적·autosave가
    // 마운트 직후 "변경됨"이 된다. setEditable(editable, false)가 지키는 불변식의 회귀 감시.
    await expect(args.onUpdate).not.toHaveBeenCalled();
  },
};

/** 읽기 전용. 타이핑해도 내용이 바뀌지 않는다. */
export const ReadOnly: Story = {
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
 * 마크다운 단축 입력 — 명세 209행이 제목·목록·코드 3종을 요구한다.
 *
 * 구현 코드가 0줄이라(StarterKit의 input rule) 검증을 빠뜨리기 쉽다. 그런데 "StarterKit이
 * 준다"는 건 우리의 가정이고, StarterKit 옵션을 나중에 건드리면 조용히 깨진다.
 * 라이브러리를 테스트하는 게 아니라 명세 요구가 만족되는지를 본다.
 */
export const MarkdownShortcuts: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const surface = canvas.getByRole('textbox');

    await userEvent.click(surface);

    await userEvent.keyboard('# 제목이 된다{Enter}');
    await expect(surface.querySelector('h1')).not.toBeNull();

    await userEvent.keyboard('- 목록이 된다{Enter}{Enter}');
    await expect(surface.querySelector('ul li')).not.toBeNull();

    // StarterKit codeBlock input rule은 /^```[\s\n]$/ — 백틱 3개 "뒤의 공백"이 방아쇠다.
    await userEvent.keyboard('``` ');
    await expect(surface.querySelector('pre code')).not.toBeNull();
  },
};

/**
 * 스키마에 없는 노드가 들어오면 onContentError가 불린다.
 *
 * enableContentCheck를 켜지 않으면 ProseMirror가 말없이 버린다. 지금은 픽스처만 넣어
 * 티가 안 나지만, blocks[]가 들어올 때 claim_section이 사라지고도 화면은 멀쩡해 보인다.
 * table은 이번 범위에 없는 노드라 검증 표본으로 쓴다(다음 단계에 TableKit이 붙으면
 * 다른 미지 노드로 바꾼다).
 */
export const InvalidContentIsReported: Story = {
  args: {
    onContentError: fn(),
    initialContent: {
      type: 'doc',
      content: [{ type: 'table', content: [] }],
    },
  },
  play: async ({ args }) => {
    await expect(args.onContentError).toHaveBeenCalled();
  },
};
