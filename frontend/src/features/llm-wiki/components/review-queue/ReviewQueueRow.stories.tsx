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
        '아바타는 공용 `shared/components/ui/avatar`의 size=small(25px)이다 — 폴백·isSafeUrl 가드가 컴포넌트 안에 있어 행에서 되풀이하지 않는다.',
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
        '아바타 radius/xl 12 = rounded-xl, 테두리 #F4F4F5 = Line/Normal/Assistive = border-line-normal-assistive. 공용 Avatar 기본값(radius 1000 + Fill/Normal/Strong #F7F7F8)과 다르다 — 디자인 시스템 원본 imagebox/profile(582:2674)이 아니라 이 목록의 인스턴스 13개가 전부 덮어쓴 값이라 className으로 되덮었다. 어느 쪽이 의도인지는 디자이너 확인 대상.',
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

/** 목록 폭 슬롯. 행 자체는 폭을 갖지 않으므로 슬롯이 폭을 준다. */
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

    // 신뢰도 숫자는 행에 노출하지 않는다.
    await expect(canvas.queryByText(/0\.62|62%/)).toBeNull();
    // 유형도 마찬가지다. 체계가 미정이라 어떤 형태로도 행에 나오면 안 된다.
    await expect(canvas.queryByText(/publish|발행/)).toBeNull();

    const row = canvas.getByRole('button');
    // 비선택 행은 채움이 없다 — 발명하지 않는다.
    await expect(window.getComputedStyle(row).backgroundColor).toBe('rgba(0, 0, 0, 0)');
    await expect(row).not.toHaveAttribute('aria-current');

    // 공용 Avatar 위에 덮은 radius·테두리가 tailwind-merge를 통과했는지 잰다.
    // 덮기가 풀리면 Avatar 기본값으로 조용히 돌아간다.
    const avatar = canvasElement.querySelector('svg[viewBox="0 0 40 40"]')?.parentElement;
    await expect(avatar).not.toBeUndefined();
    const avatarStyle = window.getComputedStyle(avatar as HTMLElement);
    await expect(avatarStyle.borderTopLeftRadius).toBe('12px');
    await expect(avatarStyle.borderTopColor).toBe('rgb(244, 244, 245)');
    await expect(Math.round((avatar as HTMLElement).getBoundingClientRect().width)).toBe(25);

    await userEvent.click(row);
    await expect(args.onSelect).toHaveBeenCalledWith('proposal-payment-retry-v3');
  },
};

/** 선택된 행 — 중립 회색 채움을 갖는다. */
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

/** 에러(충돌) 아이콘 행. 행 순서에는 관여하지 않고 아이콘 유무만 받는다. */
export const WithErrorIcon: Story = {
  args: { item: createReviewQueueItem({ hasConflictIcon: true, type: 'contradiction' }) },
  decorators: [listSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button');

    // viewBox로 에셋 교체를 잡는다.
    const icons = [...row.querySelectorAll('svg')];
    await expect(icons.some((icon) => icon.getAttribute('viewBox') === '0 0 24 24')).toBe(true);

    // 충돌 행이라고 신뢰도·유형이 새어나오면 안 된다.
    await expect(canvas.queryByText(/0\.62|62%/)).toBeNull();
    await expect(canvas.queryByText(/contradiction|모순/)).toBeNull();
  },
};

/**
 * 병합 행 — add_small 칩 + 들여쓴 둘째 줄.
 * 둘째 줄의 의미가 미확정이라 도메인 타입이 아닌 프레젠테이션 prop으로만 받는다.
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

    // 둘째 줄은 칩 너비만큼 들여써진다 — 빠지면 두 줄이 구분되지 않는다.
    await expect(secondary.getBoundingClientRect().left).toBeGreaterThan(primary.getBoundingClientRect().left);
  },
};

/** 좁은 슬롯 + 긴 제목. 행은 px 폭을 갖지 않고, 제목은 한 줄 말줄임이어야 한다. */
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

    // 폭은 슬롯이 준다 — 행에 고정 폭이 박혔다면 여기서 깨진다.
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
