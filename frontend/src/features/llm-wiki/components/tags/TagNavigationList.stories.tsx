import type { Decorator, Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { TAG_FIXTURES } from '../../fixtures/llmWikiFixtures';
import type { TagItem } from '../../types/llmWikiModel';
import TagNavigationList from './TagNavigationList';

const meta = {
  title: 'Compositions/LLM Wiki/Tags/TagNavigationList',
  component: TagNavigationList,
  tags: ['autodocs'],
  args: { tags: TAG_FIXTURES, onTagClick: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17762-103078',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17762:103078',
      },
      viewport: { width: 280, height: 300 },
      states: ['default(selected)', 'no-selection', 'long-name-truncation', 'scroll'],
      reuseNotes: [
        '대시보드 "태그 카테고리" 영역(17757:57635)의 2단 탐색 중 좌측 목록이다. 우측은 선택 태그의 문서 목록(17762:103119)이고 이 컴포넌트는 좌측만 담당한다.',
        'arrow_right2.svg는 리포에 이미 있고 마스크 id가 mask0_665_7491 = Figma icon/arrow_right2(665:7491)와 정확히 일치한다 — 신규 export 없음. fill="currentColor"라 색은 클래스가 준다.',
        '영역 헤더의 검색바(17757:57637)와 "+" 아이콘 버튼은 만들지 않았다 — 태그 어휘 관리(신설)는 이 탐색 리스트의 관심사가 아니라 영역 셸의 것이다.',
      ],
      dataNotes: [
        '8/7 Figma 재확인 결과 좌측 목록(17762:103078)은 그룹 헤더 없는 평평한 태그 목록이다 — 8행 전부 같은 구조(텍스트 + arrow_right2)이고 카테고리 머리글이 없다. MVP 명세 §11도 "태그 계층 구조"를 범위 밖으로 명시했다. 그래서 계획 초안의 TagCategory 그룹핑을 버리고 TagItem 평면 목록으로 계약을 고쳤다.',
        '문서 건수를 행에 표시하지 않는다 — 시안 행은 텍스트(fill) + 아이콘 24뿐이고 건수 자리가 없다. TagItem.documentCount는 명세 §6 유래 계약 보존용이라 남겼고, Default play가 미노출을 가드한다.',
        '태그 자동 부여 UI는 만들지 않는다 — 명세 "추후 논의"(킥오프 §6). 이 컴포넌트는 탐색 리스트만이다.',
        '신호 유형(요구·버그·질문·기타)은 기능 태그와 별개 개념이라 이 목록에 섞지 않는다.',
        '태그 0건 빈 상태·로딩 스토리는 만들지 않는다 — 디자인 MISSING(대시보드 감사).',
      ],
      tokenNotes: [
        '태그명·아이콘 모두 heading(sb)/small = text-heading-small(15/1.5/600/-0.005em).',
        '비선택 #6D7882 = Text/Normal/Alternative = text-text-normal-alternative, 아이콘은 Icon/Normal/Neutral = text-icon-normal-neutral(같은 #6D7882).',
        '선택 #3385FF = Text/Primary/Assistive = text-text-primary-assistive, 아이콘은 Icon/Primary/Assistive = text-icon-primary-assistive(같은 #3385FF).',
        '우측 구분선 #EAEBEC = Line/Normal/Neutral = border-line-normal-neutral. Figma strokeWeight가 "0px 1px 0px 0px"라 border-r 한 면뿐이다.',
      ],
      layoutNotes: [
        '폭 280을 컴포넌트에 박지 않았다 — 280은 2단 레이아웃에서 좌측 열이 갖는 값이고(우측 열은 fill), 열 배분은 부모 셸의 결정이다. 스토리 슬롯이 280을 준다.',
        '높이도 마찬가지다. Figma는 300 고정 + overflowScroll y인데, 300은 양쪽 열이 공유하는 값이라 컴포넌트는 h-full + overflow-y-auto로 슬롯 높이를 따른다.',
        '고정 치수는 행 높이 24(h-6)와 아이콘 24(size-6) 둘뿐이고 둘 다 컨트롤 크기다. 패딩 20(p-5) · 행 간 gap 16(gap-4) · 행 내 gap 12(gap-3).',
        '폭 흡수는 태그명 슬롯 하나뿐이다(min-w-0 flex-1 truncate) — Figma에서도 텍스트가 fill, 아이콘이 fixed 24다. 축소 순서는 태그명 말줄임이 전부이고 가로 스크롤은 없다.',
      ],
      interactionNotes: [
        'hover 채움을 넣지 않았다 — Figma 행 노드에 fills가 없고 hover 정의도 없다. 선택 상태만 색으로 구분된다.',
        '선택 행은 aria-current="true"다. 화살표 아이콘은 aria-hidden이라 버튼 접근명은 태그명 그대로다.',
      ],
    }),
  },
} satisfies Meta<typeof TagNavigationList>;

export default meta;
type Story = StoryObj<typeof TagNavigationList>;

/** Figma 좌측 열 슬롯(280×300). 컴포넌트가 폭·높이를 갖지 않으므로 슬롯이 준다. */
const paneSlot: Decorator = (Story) => (
  <div className="h-75 w-70">
    <Story />
  </div>
);

const GRAY = 'rgb(109, 120, 130)'; // #6D7882 Text/Normal/Alternative
const BLUE = 'rgb(51, 133, 255)'; // #3385FF Text/Primary/Assistive

/**
 * Figma가 렌더한 그대로의 상태 — 첫 행이 선택(파랑)이고 나머지는 중립이다.
 */
export const Default: Story = {
  args: { selectedTagId: 'tag-retry' },
  decorators: [paneSlot],
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: '재시도 정책' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '환불' })).toBeInTheDocument();
    await expect(canvas.getAllByRole('button')).toHaveLength(TAG_FIXTURES.length);

    // 카테고리 그룹 머리글이 있으면 안 된다 — 계층 구조는 명세 §11 범위 밖이고 시안에도 없다.
    await expect(canvas.queryByRole('heading')).toBeNull();
    await expect(canvas.queryByText('결제')).toBeNull();
    await expect(canvas.queryByText('계정')).toBeNull();

    // 문서 건수도 행에 새어나오면 안 된다 — 시안 행에 건수 자리가 없다.
    for (const tag of TAG_FIXTURES) {
      await expect(canvas.queryByText(String(tag.documentCount))).toBeNull();
    }

    const selected = canvas.getByRole('button', { name: '재시도 정책' });
    const unselected = canvas.getByRole('button', { name: '환불' });
    await expect(selected).toHaveAttribute('aria-current', 'true');
    await expect(unselected).not.toHaveAttribute('aria-current');
    await expect(window.getComputedStyle(selected).color).toBe(BLUE);
    await expect(window.getComputedStyle(unselected).color).toBe(GRAY);

    // 비선택 행에 채움을 발명하지 않았다 — Figma 행 노드에 fills가 없다.
    await expect(window.getComputedStyle(unselected).backgroundColor).toBe('rgba(0, 0, 0, 0)');

    await userEvent.click(unselected);
    await expect(args.onTagClick).toHaveBeenCalledWith('tag-refund');
  },
};

/**
 * 아직 아무 태그도 고르지 않은 목록. 새 시각이 아니라 Figma 비선택 행(17762:103082 외 7행) 스타일이
 * 전 행에 적용된 것뿐이다 — 빈 상태가 아니므로 금지 목록에 걸리지 않는다.
 */
export const NoSelection: Story = {
  decorators: [paneSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    for (const button of canvas.getAllByRole('button')) {
      await expect(button).not.toHaveAttribute('aria-current');
      await expect(window.getComputedStyle(button).color).toBe(GRAY);
    }
  },
};

/**
 * 긴 태그명 + Figma보다 좁은 슬롯. 목록은 px 폭을 갖지 않아야 하고(200 슬롯이면 200),
 * 태그명은 감기지 않고 잘려야 하며 화살표는 줄지 않아야 한다.
 */
export const LongNameInNarrowSlot: Story = {
  args: {
    tags: [
      { id: 'tag-long', name: '결제 승인 실패 재시도 정책 및 PG사별 예외 처리 text text text', documentCount: 12 },
      ...TAG_FIXTURES,
    ],
    selectedTagId: 'tag-long',
  },
  decorators: [
    (Story) => (
      <div className="h-75 w-50">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const list = canvas.getByRole('list');
    const row = canvas.getAllByRole('button')[0];
    const label = within(row).getByText(/결제 승인 실패 재시도 정책/);

    // 폭은 슬롯이 준다 — 280px이 박혔다면 여기서 깨진다.
    await expect(list.getBoundingClientRect().width).toBe(200);
    await expect(list.scrollWidth).toBeLessThanOrEqual(list.clientWidth);

    // 태그명은 한 줄 말줄임이다. 감기면 행 높이 24가 무너져 목록 리듬이 어긋난다.
    await expect(label.scrollWidth).toBeGreaterThan(label.clientWidth);
    await expect(label.getClientRects()).toHaveLength(1);
    await expect(row.getBoundingClientRect().height).toBe(24);

    // 화살표는 축소 대상이 아니다 — Figma에서 fixed 24다.
    const icon = row.querySelector('svg');
    await expect(icon?.getBoundingClientRect().width).toBe(24);
  },
};

/**
 * Figma 좌측 열은 8행을 300px 안에 담아 이미 넘친다(20 + 8×24 + 7×16 + 20 = 344).
 * overflowScroll y가 노드에 정의돼 있으므로 목록 자신이 스크롤해야 하고, 슬롯을 밀어내면 안 된다.
 */
export const ScrollsWithinPane: Story = {
  args: {
    tags: Array.from(
      { length: 8 },
      (_, index): TagItem => ({
        id: `tag-${index}`,
        name: `태그 text text text text ${index + 1}`,
        documentCount: index + 1,
      }),
    ),
    selectedTagId: 'tag-0',
  },
  decorators: [paneSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const list = canvas.getByRole('list');

    await expect(list.getBoundingClientRect().height).toBe(300);
    await expect(list.scrollHeight).toBeGreaterThan(list.clientHeight);
  },
};
