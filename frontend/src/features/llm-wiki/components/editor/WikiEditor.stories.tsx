import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { EDITOR_PHASE2_DOC, EDITOR_SKELETON_DOC } from '../../fixtures/llmWikiEditorFixtures';
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
 *
 * ── Docs 페이지에는 Empty·WithContent 둘만 싣는다 ──────────────────
 * 나머지 스토리에 tags: ['!autodocs']가 붙어 있다.
 *
 * 이유: Docs는 파일의 모든 스토리를 한 화면에 동시 마운트한다. 에디터 하나가
 * ProseMirror view + DragHandle + BubbleMenu + Suggestion 2개(슬래시·이모지)를
 * 들고 있어서 그 비용이 인스턴스 수만큼 곱해진다 — 사이드바에서 컴포넌트를 누르면
 * Docs가 기본 착지라, 열자마자 페이지가 멈춘다는 보고가 있었다.
 * 실측: 태그 적용 전 .ProseMirror 17개 → 적용 후 3개(프리뷰 + 스토리 2개).
 * 스토리 목록과 자동 테스트에는 16개 전부 그대로 남으므로 커버리지 손실은 없다.
 * ────────────────────────────────────────────────────
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
  tags: ['!autodocs'],
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
 * slashCommand.onKeyDown → WikiEditor.handleMenuKeyDown → menuRef → SlashMenu useImperativeHandle
 * 로 이어지는, 태스크 3개를 가로지르는 유일한 런타임 이음새의 회귀 감시다.
 * (조합 중 Enter 같은 IME 경로는 자동화 불가 — 상단 수동 체크리스트가 담당한다.)
 */
export const SlashMenuKeyboard: Story = {
  tags: ['!autodocs'],
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

/**
 * 노션식 트리거(스펙 §12): 단어 끝에 바로 /를 쳐도 메뉴가 열린다.
 * 1차의 "and/ 차단" 규칙을 사용자 결정으로 대체했다 — 이 스토리가 그 결정의 회귀 감시다.
 */
export const SlashAfterWordOpens: Story = {
  tags: ['!autodocs'],
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
  tags: ['!autodocs'],
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

/**
 * 플로팅 서식 툴바(스펙 §12) — 텍스트를 선택하면 뜨고, 굵게를 누르면 strong이 생긴다.
 * 글리프는 문자 기반(B·I·U·S) — 서식 아이콘 자산 부재의 임시 시각(노션 방식과 동일).
 */
export const FormattingToolbarStory: Story = {
  tags: ['!autodocs'],
  name: 'Formatting Toolbar',
  args: { initialContent: EDITOR_SKELETON_DOC },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);
    const surface = canvas.getByRole('textbox');

    // 선택 전에는 툴바가 없다
    await expect(body.queryByRole('toolbar', { name: '텍스트 서식' })).toBeNull();

    // tripleClick은 헤드리스에서 PM 선택으로 이어지지 않고(detail 시퀀스가 handleTripleClick에 닿지 않음),
    // user-event의 {Home}/{End}는 contenteditable에서 "Not implemented"다. DOM Range를 직접 걸면
    // 브라우저가 selectionchange를 발사하고 PM이 그걸 집는다 — 실브라우저 수동 재현과 같은 경로.
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
    // 마크 적용이 노드 DOM을 재생성할 수 있어 stale 참조 대신 surface에서 재조회한다
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
  tags: ['!autodocs'],
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

/**
 * 드래그 핸들 옆 + 버튼 — 현재 블록 아래에 빈 문단을 만들고 슬래시 메뉴를 연다.
 * '/' 삽입 경로를 그대로 타므로 메뉴 상태 배선이 중복되지 않는다.
 */
export const AddBlockButton: Story = {
  tags: ['!autodocs'],
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

    // 캐럿을 블록 안에 둔다 — 헤드리스에서는 hover가 DragHandle의 mousemove 추적으로 이어지지
    // 않아 + 버튼이 "선택 블록 뒤 삽입" 폴백 경로를 탄다(실브라우저에서는 호버 블록 기준).
    await userEvent.click(within(surface).getByText('기준 블록'));

    // 핸들은 호버 전까지 visibility:hidden이고 user-event는 숨은 요소 클릭을 조용히 무시한다.
    // 실 UX(호버→표시→클릭)는 실브라우저에서 검증했다 — 여기서는 배선 회귀만 보므로 네이티브 클릭.
    const addButton = await canvas.findByRole('button', { name: '아래에 블록 추가' });
    (addButton as HTMLButtonElement).click();

    // 슬래시 메뉴가 열린다 — '/' 삽입이 Suggestion을 트리거했다는 뜻
    await expect(await body.findByText('제목 1')).toBeInTheDocument();
  },
};

/** 콜아웃 — 커스텀 노드가 블록을 감싸고 다시 풀 수 있다. */
export const CalloutToggle: Story = {
  tags: ['!autodocs'],
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

/**
 * 드래그 핸들. 명세·Figma 근거가 없는 유일한 기능이라 시각을 최소로 뒀다
 * (drag_indicator.svg + 호버 시 노출). 시안 요청은 design-request에 올라가 있다.
 */
export const DragHandle: Story = {
  tags: ['!autodocs'],
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

/** 2차 블록 JSON 로드 — 체크박스·콜아웃·표가 blocks[] 형태 그대로 렌더된다. */
export const WithPhase2Content: Story = {
  tags: ['!autodocs'],
  args: { initialContent: EDITOR_PHASE2_DOC, onContentError: fn() },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const surface = canvas.getByRole('textbox');

    await expect(surface.querySelectorAll('ul[data-type="taskList"] input[type="checkbox"]')).toHaveLength(2);
    await expect(surface.querySelector('ul[data-type="taskList"] input[type="checkbox"]:checked')).not.toBeNull();
    await expect(surface.querySelector('div[data-type="callout"]')).toHaveTextContent('새벽 배치 기준');
    await expect(surface.querySelectorAll('table th')).toHaveLength(2);
    // 전부 스키마 안이어야 한다 — 하나라도 밖이면 조용한 소실이 시작된다
    await expect(args.onContentError).not.toHaveBeenCalled();
  },
};

/** `:` 이모지 서제스천 — :sm 검색 → 선택 → 이모지 문자 삽입. */
export const EmojiPicker: Story = {
  tags: ['!autodocs'],
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
  tags: ['!autodocs'],
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
  tags: ['!autodocs'],
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
 * image는 범위 밖(영구 제외) 노드라 검증 표본으로 쓴다 — 2차에서 table이 스키마에
 * 들어오면서 이전 표본을 교체했다.
 */
export const InvalidContentIsReported: Story = {
  tags: ['!autodocs'],
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
