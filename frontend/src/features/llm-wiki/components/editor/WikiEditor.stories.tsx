import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
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
      states: ['empty', 'slash-menu-open', 'drag-handle'],
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
