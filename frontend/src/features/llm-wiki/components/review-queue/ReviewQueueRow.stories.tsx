import type { Decorator, Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { createReviewQueueItem } from '../../fixtures/llmWikiFixtures';
import ReviewQueueRow from './ReviewQueueRow';

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/ReviewQueueRow',
  component: ReviewQueueRow,
  tags: ['autodocs'],
  args: { onSelect: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17849-106767',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17849:106767',
      },
      viewport: { width: 300, height: 120 },
      states: ['default', 'selected', 'with-error-icon', 'merge-second-line(meaning-tbd)'],
      reuseNotes: [
        '검토 큐 좌측 목록(17564:126942, 폭 300)의 행이다. 목록 13행 중 12행이 기본형(17849:106767), 최상단 1행만 에러 아이콘 + 선택 채움(17564:126946)이다.',
        'error.svg(마스크 id mask0_389_1866 = Figma icon/error 389:1866)·add_small.svg(mask0_46_1623 = icon/add_small 46:1623)는 리포에 이미 있는 에셋과 컴포넌트 id가 정확히 일치한다 — 신규 export 없음.',
        '아바타는 AgentCard(agent-studio)의 관례를 그대로 따랐다: size-6.25 원형 + default_profile.svg 폴백 + isSafeUrl 가드. 공용 아바타 컴포넌트는 리포에 아직 없다.',
      ],
      dataNotes: [
        '행에 신뢰도를 표시하지 않는다 — 감사 판정 MISSING(필터에만 존재). fixture의 confidence는 계약 보존용이라 이 컴포넌트는 props로 받지도 않는다. Default·WithErrorIcon play가 미노출을 가드한다.',
        '유형 배지도 만들지 않는다 — 백엔드 3종↔명세 6유형 불일치로 체계 미정. 8/6 재확인에서도 행에는 유형 표기가 없었다. 대신 상세 패널 헤더에 "유형 / 상태 태그"(17845:105886) 자리표시 텍스트가 새로 생겼다 — 배지가 붙는다면 행이 아니라 상세다.',
        '빈 큐·로딩·에러·처리 피드백(pending/성공/실패)·stale 거부 스토리는 만들지 않는다(감사 §7 금지 목록).',
        '목록 헤더 건수는 "1"인데 행은 13개다(Figma 목업 불일치) — 건수는 이 컴포넌트의 관심사가 아니라 목록 셸의 것이다.',
      ],
      tokenNotes: [
        '제목 #33363D = text-text-normal-normal, heading(sb)/small = text-heading-small.',
        '작성자명도 #33363D(text-text-normal-normal), 대기 기간만 #B1B8BE = text-text-normal-assistive. 둘 다 body(md)/xsmall = text-body-xsmall.',
        '행 하단 구분선 #EAEBEC = Line/Normal/Neutral = border-line-normal-neutral, 1px 하단만.',
        '선택 채움 #F7F7F8 = Fill/Normal/Strong = bg-fill-normal-strong. 비선택 행은 fills=[] — 투명이다.',
        '에러 아이콘 #FF6363 = Accent/Red/Default = text-accent-red-default. add_small 칩은 #F7F7F8 배경(bg-fill-normal-strong) + radius/rounded 1000(rounded-full) + 아이콘 #6D7882 = text-icon-normal-neutral.',
        '아바타 radius/xl 12 = rounded-xl, 테두리 #F4F4F5 = Line/Normal/Assistive = border-line-normal-assistive.',
      ],
      layoutNotes: [
        '행은 세로 스택(padding 12/16, gap 12)이고 폭은 Figma sizing=fill이라 px를 박지 않았다 — 목록 폭 300은 부모 것이다. FluidWidth 스토리가 400px 슬롯에서 400을 확인한다.',
        '높이도 결과값이다(12 + 제목 23 + 12 + 메타 25 + 12 = 84). h-*를 두지 않는다.',
        '폭 흡수는 레벨당 하나다: 행 전체는 제목 슬롯, 메타 행은 작성자명 슬롯. 대기 기간·아바타·아이콘은 shrink-0.',
        '축소 순서는 제목 truncate → 작성자명 truncate이고 가로 스크롤은 없다. Figma 목록 렌더에서 제목이 한 줄 말줄임이다.',
        '고정 치수는 아이콘 24 · add_small 22 · 아바타 25 세 개뿐이고 전부 컨트롤 크기다.',
      ],
      interactionNotes: [
        'hover 채움을 넣지 않았다 — Figma 행 노드에 hover 정의가 없다(비선택 행 fills=[]). 목록에서 hover가 필요하면 디자이너 확인이 선행되어야 한다.',
      ],
    }),
  },
} satisfies Meta<typeof ReviewQueueRow>;

export default meta;
type Story = StoryObj<typeof ReviewQueueRow>;

/** Figma 목록 폭 300px 슬롯. 행 자체는 폭을 갖지 않으므로 슬롯이 폭을 준다. */
const listSlot: Decorator = (Story) => (
  <div className="w-75 overflow-hidden">
    <Story />
  </div>
);

export const Default: Story = {
  args: { item: createReviewQueueItem() },
  decorators: [listSlot],
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('결제 승인 실패 시 재시도 정책 변경안')).toBeInTheDocument();
    await expect(canvas.getByText('직원10')).toBeInTheDocument();
    await expect(canvas.getByText('15시간 전')).toBeInTheDocument();

    // 신뢰도 숫자가 행에 노출되면 안 된다 — 감사 판정 MISSING.
    await expect(canvas.queryByText(/0\.62|62%/)).toBeNull();
    // 유형도 마찬가지다. 체계가 미정이라 어떤 형태로도 행에 나오면 안 된다.
    await expect(canvas.queryByText(/publish|발행/)).toBeNull();

    const row = canvas.getByRole('button');
    // 비선택 행은 Figma fills=[] — 채움을 발명하지 않았다.
    await expect(window.getComputedStyle(row).backgroundColor).toBe('rgba(0, 0, 0, 0)');
    await expect(row).not.toHaveAttribute('aria-current');

    await userEvent.click(row);
    await expect(args.onSelect).toHaveBeenCalledWith('proposal-payment-retry-v3');
  },
};

/**
 * 선택된 행(17564:126946). 목록 최상단 행이 상세와 함께 채움 #F7F7F8을 갖는다.
 * 같은 행이 에러 아이콘도 달고 있어 "채움 = 선택"인지 "채움 = 충돌"인지 Figma만으로는 갈리지 않는데,
 * 충돌 색은 대시보드에서 붉은 계열(#FFFAFA)이고 여기 채움은 중립 회색이라 선택으로 읽었다.
 */
export const Selected: Story = {
  args: { item: createReviewQueueItem(), selected: true },
  decorators: [listSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button');

    await expect(row).toHaveAttribute('aria-current', 'true');
    await expect(window.getComputedStyle(row).backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
  },
};

/**
 * 에러(충돌) 아이콘 행. 상단 고정 규칙인지는 UNKNOWN이라 이 컴포넌트는 순서에 관여하지 않는다 —
 * 아이콘 유무만 받는다.
 */
export const WithErrorIcon: Story = {
  args: { item: createReviewQueueItem({ hasConflictIcon: true, type: 'contradiction' }) },
  decorators: [listSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button');

    // icon/error(389:1866) = error.svg. viewBox 24로 에셋 교체를 잡는다.
    const icons = [...row.querySelectorAll('svg')];
    await expect(icons.some((icon) => icon.getAttribute('viewBox') === '0 0 24 24')).toBe(true);

    // 충돌 행이라고 신뢰도·유형이 새어나오면 안 된다.
    await expect(canvas.queryByText(/0\.62|62%/)).toBeNull();
    await expect(canvas.queryByText(/contradiction|모순/)).toBeNull();
  },
};

/**
 * add_small + 들여쓴 둘째 줄 행. Figma 레이어 이름이 **"병합"**(17762:102964)이라
 * 감사 문서의 "유사 항목 묶음" 추정과 다르게 읽힌다 — 다만 둘째 줄이 병합 대상 문서 제목인지,
 * 묶인 하위 제안인지는 여전히 확정되지 않았다. 그래서 둘째 줄은 도메인 타입(ReviewQueueItemData)에
 * 넣지 않고 프레젠테이션 prop으로만 받는다. 의미가 확정되면 계약과 이름을 함께 고친다.
 */
export const MergeSecondLineMeaningTBD: Story = {
  args: {
    item: createReviewQueueItem({
      id: 'proposal-merge-refund',
      type: 'merge',
      title: '환불 문서 병합 제안',
    }),
    secondaryTitle: '환불 가능 기간 안내',
  },
  decorators: [listSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const primary = canvas.getByText('환불 문서 병합 제안');
    const secondary = canvas.getByText('환불 가능 기간 안내');
    await expect(secondary).toBeInTheDocument();

    // 둘째 줄은 add_small 칩만큼 들여써진다(칩 26 + gap 12). 들여쓰기가 빠지면 두 줄이 구분되지 않는다.
    await expect(secondary.getBoundingClientRect().left).toBeGreaterThan(primary.getBoundingClientRect().left);
  },
};

/**
 * 좁은 슬롯 + 긴 제목. 행은 px 폭이 없어야 하고(400 슬롯이면 400), 제목은 한 줄 말줄임이어야 한다.
 * 새 디자인 상태가 아니라 Default 상태를 다른 폭에서 다시 잰 것이다.
 */
export const FluidWidthAndTruncation: Story = {
  args: {
    item: createReviewQueueItem({
      title: '결제 승인 실패 시 재시도 정책 변경안 및 PG사별 예외 처리와 고객 안내 문구 표준화 제안 text text text',
      authorName: '직원10 (플랫폼 프로덕트 매니지먼트 그룹 · 결제 도메인 오너)',
    }),
  },
  decorators: [
    (Story) => (
      <div className="w-100 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button');
    const title = canvas.getByText(args.item.title);

    // 폭은 슬롯이 준다 — 행에 300px이 박혔다면 여기서 깨진다.
    await expect(row.getBoundingClientRect().width).toBe(400);
    await expect(row.scrollWidth).toBeLessThanOrEqual(row.clientWidth);

    // 제목은 감기지 않고 잘린다. 감기면 행 높이가 자라 목록 리듬이 어긋난다.
    await expect(title.scrollWidth).toBeGreaterThan(title.clientWidth);
    await expect(title.getClientRects()).toHaveLength(1);

    // 대기 기간은 줄어들지 않는다 — 축소 순서상 작성자명이 먼저 잘려야 한다.
    const waiting = canvas.getByText('15시간 전');
    await expect(waiting.scrollWidth).toBe(waiting.clientWidth);
    await expect(canvas.getByText(args.item.authorName).scrollWidth).toBeGreaterThan(
      canvas.getByText(args.item.authorName).clientWidth,
    );
  },
};
