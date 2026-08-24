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
      states: ['default(owner-none)', 'owner-single', 'owner-stack', 'selected', 'merge-second-line(meaning-tbd)'],
      reuseNotes: [
        '검토 큐 좌측 목록(17564:126942, 폭 300)의 행이다. 기본형은 17849:106767. 충돌(모순) 아이콘 행(17564:126946)은 MVP 제외 결정으로 렌더·스토리를 제거했다 — 재도입 시 error.svg(icon/error 389:1866)가 리포에 이미 있다.',
        'add_small.svg(mask0_46_1623 = icon/add_small 46:1623)는 리포에 이미 있는 에셋과 컴포넌트 id가 정확히 일치한다 — 신규 export 없음.',
        '작성자 아바타·이름은 걷어냈다(공용 Avatar 소비 지점 소멸). 시안에는 있으나 GET /knowledge-review/queue 응답에 대응 필드가 없다 — LLM 제안이라 작성자 개념이 부재하고, 시안 정리는 design-request 몫.',
        '2줄째 담당자는 8/24 시안으로 부활했다 — 시안의 아바타는 작성자가 아니라 담당자(owners)로 확정. 2인 이상 스택은 공용 AvatarGroup(max 3, 겹침 -6px) 재사용.',
      ],
      dataNotes: [
        '작성자·신뢰도는 계약에서 제거됐다 — 실 API 응답에 없다. Default play가 아바타·이름의 부재를 가드한다.',
        '담당자는 큐 응답 owners[]가 원천이다(18814:133231 정본). 없음 케이스의 대시+문구는 2026-08-24 추가 노드(18157:78646·17595:148922) 실측 — 정본 프레임(18920:96195)에는 대시가 없어 노드 간 갈림이 있고, 사용자 지시에 따라 추가 노드를 따른다.',
        '충돌(모순) 아이콘 행은 MVP 제외 — hasConflictIcon 필드는 [BE] contains_conflict 대응이라 계약만 보존하고 렌더하지 않는다.',
        '유형 배지도 만들지 않는다 — 백엔드 3종↔명세 6유형 불일치로 체계 미정. 8/6 재확인에서도 행에는 유형 표기가 없었다. 대신 상세 패널 헤더에 "유형 / 상태 태그"(17845:105886) 자리표시 텍스트가 새로 생겼다 — 배지가 붙는다면 행이 아니라 상세다.',
        '빈 큐·로딩·에러·처리 피드백(pending/성공/실패)·stale 거부 스토리는 만들지 않는다(감사 §7 금지 목록).',
        '목록 헤더 건수는 "1"인데 행은 13개다(Figma 목업 불일치) — 건수는 이 컴포넌트의 관심사가 아니라 목록 셸의 것이다.',
      ],
      tokenNotes: [
        '제목 #33363D = text-text-normal-normal, heading(sb)/small = text-heading-small.',
        '대기 기간 #B1B8BE = text-text-normal-assistive, body(md)/xsmall = text-body-xsmall.',
        '담당자 없음 대시 16×2 #EAEBEC = bg-line-normal-neutral. 라벨 "담당자" #6D7882 = text-normal-alternative, 이름 #464C53 = text-normal-neutral. 1인 아바타 25 radius 12 보더 #F4F4F5 = border-line-normal-assistive. 추가 노드의 없음 문구는 body(md)/small(15)이나 대시보드 행(15px 스케일)의 실측이라, 이 행의 2줄째 스케일(body-xsmall, 정본 18920:96195과 일치)을 따른다.',
        '행 하단 구분선 #EAEBEC = Line/Normal/Neutral = border-line-normal-neutral, 1px 하단만.',
        '선택 채움 #F7F7F8 = Fill/Normal/Strong = bg-fill-normal-strong. 비선택 행은 fills=[] — 투명이다.',
        'add_small 칩은 #F7F7F8 배경(bg-fill-normal-strong) + radius/rounded 1000(rounded-full) + 아이콘 #6D7882 = text-icon-normal-neutral.',
      ],
      layoutNotes: [
        '행은 세로 스택(padding 12/16, gap 12)이고 폭은 Figma sizing=fill이라 px를 박지 않았다 — 목록 폭 300은 부모 것이다. FluidWidth 스토리가 400px 슬롯에서 400을 확인한다.',
        '2줄째는 row gap 12 — 담당자 표시가 좌측 잔여 폭을 흡수하고 상대시각이 우측 끝이다("우측 상대시각", D-i).',
        '높이는 결과값이다 — h-*를 두지 않는다.',
        '폭을 흡수하는 슬롯은 제목 하나다. 제목은 한 줄 말줄임이고 가로 스크롤은 없다.',
        '고정 치수는 아이콘 24 · add_small 22 둘뿐이고 전부 컨트롤 크기다.',
      ],
      interactionNotes: [
        'hover 채움은 fill-normal-interaction-hover다 — Figma 행 노드에 hover 정의가 없어 사용자 결정으로 중립 interaction 토큰을 채택했다. 선택 행 위에서는 알파가 strong 채움 위에 합성된다.',
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
    await expect(canvas.getByText('15시간 전')).toBeInTheDocument();

    // 담당자 미지정 행은 대시 + 문구만 선다. 아바타 폴백 svg가 남으면 안 된다.
    await expect(canvas.getByText('담당자 없음')).toBeInTheDocument();
    await expect(canvas.queryByText('직원10')).toBeNull();
    await expect(canvasElement.querySelector('svg[viewBox="0 0 40 40"]')).toBeNull();
    // 유형도 마찬가지다. 체계가 미정이라 어떤 형태로도 행에 나오면 안 된다.
    await expect(canvas.queryByText(/publish|발행/)).toBeNull();

    const row = canvas.getByRole('button');
    // 비선택 행은 채움이 없다 — 발명하지 않는다.
    await expect(window.getComputedStyle(row).backgroundColor).toBe('rgba(0, 0, 0, 0)');
    await expect(row).not.toHaveAttribute('aria-current');

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

/** 담당자 1인 — 아바타(25, radius 12) + "담당자" 라벨 + 이름. */
export const OwnerSingle: Story = {
  args: {
    item: createReviewQueueItem({
      owners: [{ userId: 2, displayName: '직원10', profileImageUrl: null }],
    }),
  },
  decorators: [listSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('담당자')).toBeInTheDocument();
    await expect(canvas.getByText('직원10')).toBeInTheDocument();
    await expect(canvas.queryByText('담당자 없음')).toBeNull();
    // 이미지 없는 담당자는 기본 프로필로 폴백한다 — 아바타 슬롯 자체는 서야 한다.
    await expect(canvasElement.querySelector('svg[viewBox="0 0 40 40"]')).not.toBeNull();
  },
};

/** 담당자 2인 이상 — AvatarGroup 스택(최대 3) + 초과분 "+N" 칩 + "담당자" 라벨. 이름은 접힌다. */
export const OwnerStack: Story = {
  args: {
    item: createReviewQueueItem({
      owners: [
        { userId: 3, displayName: '이진수', profileImageUrl: null },
        { userId: 12, displayName: '남궁현', profileImageUrl: null },
        { userId: 4, displayName: '김하은', profileImageUrl: null },
        { userId: 5, displayName: '최민우', profileImageUrl: null },
      ],
    }),
  },
  decorators: [listSlot],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('담당자')).toBeInTheDocument();
    await expect(canvas.getByText('+1')).toBeInTheDocument();
    // 스택에는 이름이 서지 않는다 — 명단은 우측 담당자 카드 몫이다.
    await expect(canvas.queryByText('이진수')).toBeNull();
    await expect(canvasElement.querySelectorAll('svg[viewBox="0 0 40 40"]')).toHaveLength(3);
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

    // 대기 기간은 짧아 잘리지 않는다 — 축소 부담은 제목이 진다.
    const waiting = canvas.getByText('15시간 전');
    await expect(waiting.scrollWidth).toBe(waiting.clientWidth);
  },
};
