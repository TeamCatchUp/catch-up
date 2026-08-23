import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import {
  BASE_WIKI_BLOCKS,
  LONG_BASE_WIKI_BLOCKS,
  LONG_PROPOSED_WIKI_BLOCKS,
  PROPOSED_BLOCK_CHANGES,
  PROPOSED_WIKI_BLOCKS,
  SINGLE_MODIFIED_BLOCK_CHANGES,
} from '../../../fixtures/llmWikiDiffFixtures';
import { buildBlockDiff } from '../../../utils/diff/buildBlockDiff';
import BlockDiffCard from './BlockDiffCard';

const entries = buildBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS, PROPOSED_BLOCK_CHANGES);
const modifiedEntry = entries.find((e) => e.kind === 'modified')!;
const addedEntry = entries.find((e) => e.kind === 'added')!;
const removedEntry = entries.find((e) => e.kind === 'removed')!;
const [longEntry] = buildBlockDiff(LONG_BASE_WIKI_BLOCKS, LONG_PROPOSED_WIKI_BLOCKS, SINGLE_MODIFIED_BLOCK_CHANGES);

/** 검토자가 반려에 남긴 글. 서버가 판정과 함께 저장해 상세로 다시 내려준다 */
const REJECTION_REASON = '근거 VOC가 동일 고객사 3건이라 일반화하기 이르다';

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/BlockDiffCard',
  component: BlockDiffCard,
  tags: ['autodocs'],
  args: { onApprove: fn(), onReject: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17849-106310',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17849:106310',
      },
      viewport: { width: 700, height: 420 },
      states: [
        'modified',
        'added',
        'removed',
        'collapsed',
        'rejected',
        'approved',
        'long-text',
        'no-reason',
        'no-review-permission',
        'no-reject-path',
      ],
      reuseNotes: [
        '버튼은 공용 Button(box-solid-primary/box-outline-gray/icon-only-gray)을 그대로 쓴다 — 시안의 Box Button small(30px)·Icon button small(28px) 대응. 아이콘 버튼 28px는 AgentCard 관례대로 size="sm" + size-7이다.',
        '헤더 배치: 셰브런 · 제목 · 반려 · 승인. 판정이 승인·반려 둘로 정리되면서 되돌리기(rotate)가 빠지고 삭제가 반려로 바뀌었다(8/7) — 백엔드 approve/reject와 1:1이다.',
        '시안의 연필(개별 블록 수정) 아이콘은 렌더하지 않는다 — 그 기능이 MVP 제외로 확정됐고(8/10), 닿는 곳 없는 버튼은 "구현됨"으로 오독된다. 시안 정리 요청은 검토 큐 design-request 수동 추가 절에 있다.',
        '셰브런 자산 대조 완료: arrow_dropdown_right(mask0_16877_80457) = 접힘 시안 icon/arrow_right(16877:80457), arrow_dropdown_down(mask0_6413_79613) = icon/arrow_drop_down(6413:79613). backspace.svg(mask0_17998_46476)는 8/7 Figma에서 신규 내려받았다.',
        '"반려됨" 배지는 Figma가 Box Button state=Inactive로 그렸지만 누를 수 없는 표시라 span으로 낸다 — 토큰(bg-fill-normal-interaction-inactive·border-line-normal-normal·text-text-normal-assistive)은 그 변형 그대로다.',
        '연필 버튼의 aria-label은 "이 블록 수정"이다 — 섹션 헤더의 전역 "직접 수정"과 접근성 이름이 겹치면 안 된다.',
      ],
      dataNotes: [
        '엔트리는 픽스처 blocks[] 쌍과 서버 변경 목록에 buildBlockDiff를 돌려 얻는다 — 계산과 표시가 같은 파이프라인을 지나는 것을 스토리가 상시 검증한다.',
        'removed 카드(빨강 단일 전폭)는 시안에 없는 프론트 잠정안이다 — added(초록 단일 전폭)의 거울상. design-request 9번으로 확인 요청 상태.',
        '카드 제목·"수정된 이유"의 실카피는 시안이 placeholder라 미정(감사 UNKNOWN 카피 미정). 빈 diff·로딩·에러 스토리는 만들지 않는다(MISSING).',
        'removed 카드에는 사유가 붙지 않는다 — 빠진 블록은 변경안에 자리가 없어 change_reason이 실릴 곳이 없다.',
        '"수정된 이유"는 서버가 만든 요약 문구다(새 섹션·산문 갱신·근거 N건 추가·M건 폐기) — 사람이 쓴 설명이 아니다.',
        '본문은 narrative(사람용 산문)가 정본이고, 없는 블록(옛 데이터)만 body로 폴백한다 — Modified가 산문 경로, Added가 폴백 경로를 밟는다.',
        'canReview=false면 판정 버튼이 사라지고 열람만 남는다 — 값은 서버가 계산한 can_review이고 프론트는 재계산하지 않는다. 비활성+툴팁 안은 디자이너 미결이라 숨김으로 간다.',
        '판정이 끝난 카드(approved·rejected)는 액션이 빠지고 접힌 채로 남는다. 반려만 배지가 서고 승인은 대응 시각이 없다 — 접힘 여부로만 미판정과 갈린다(알려진 구멍).',
        '반려 사유는 서버가 판정과 함께 저장한 검토자 글이다 — 반려된 카드에서만 "수정된 이유"와 같은 패널로 낸다. 레이블 문구는 시안 없이 정한 자작분이다.',
      ],
      tokenNotes: [
        '패널 색은 8/7 실측 확정(17849:106867·17848:106179) — removed: bg-red-1(#FFFAFA)/좌측 바 2px red-40, added: bg-green-5(#E6FAF2)/좌측 바 2px green-60(#00985A). 패널 자체에는 padding도 radius도 없다.',
        '줄은 padding 8/12 = py-2 px-3, 타이포는 Reading/body(md)/small = text-reading-body-md-small(15px/1.75). 일반 body-small(1.5)이 아니다 — 줄 높이 42가 여기서 나온다.',
        '초록 강조 #B0EFD5=green-20 + 좌우 2px(px-0.5)는 시안에 실재한다(17849:106894, 호버 행 안의 텍스트 hug 프레임). 다만 단어 단위인지 줄 전체인지는 placeholder라 갈리지 않아 단어 단위는 프론트 결정.',
        '빨강 강조 red-10(#FED5D5)은 시안 대응물이 없다 — 빨강 행이 전부 빈 프레임이라 초록의 거울상으로 잡았다. design-request 10번 확인 대기.',
        '박스 버튼은 h-7.5(30)을 명시한다 — outline은 1px 테두리로 30이 되는데 solid는 28이라 나란히 두면 어긋난다. 공용 Button 특성이고 리포 관례(pending/page.tsx의 h-11.5)를 따랐다.',
        '카드 테두리 #EAEBEC=border-line-normal-neutral·radius 12=rounded-xl. 수정된 이유 바(17849:106254, 8/7 개정): 세로 배치 gap 8 — 레이블 #6D7882=text-text-normal-alternative body-xsmall + 본문 #464C53=text-text-normal-neutral body-small, 배경 #F7F7F8=bg-fill-normal-strong.',
      ],
      interactionNotes: [
        '줄 호버 하이라이트는 패널별 독립이고 클릭 동작이 없다(시안 우측 첫 행 진한 초록 #D9F7EB=green-10 = 호버 상태, 2026-08-07 확인).',
        '접기는 uncontrolled — 셰브런이 본문·수정된 이유를 함께 숨긴다. 아이콘은 접힘 arrow_dropdown_right / 펼침 arrow_dropdown_down(자산 마스크 id가 시안 icon/arrow_drop_down 6413:79613과 일치).',
      ],
    }),
  },
} satisfies Meta<typeof BlockDiffCard>;

export default meta;
type Story = StoryObj<typeof BlockDiffCard>;

export const Modified: Story = {
  args: { entry: modifiedEntry },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    // 본문은 산문 축이다 — body의 값 표기(1회/3회까지)는 화면에 실리지 않는다
    await expect(canvasElement.textContent).toContain('한 번 더');
    await expect(canvasElement.textContent).toContain('세 번까지');
    await expect(canvasElement.textContent).not.toContain('3회까지');
    // 좌우 패널에서 바뀐 단어가 강조된다
    await expect(canvasElement.querySelectorAll('[class*="bg-green-20"]').length).toBeGreaterThan(0);
    await expect(canvasElement.querySelectorAll('[class*="bg-red-10"]').length).toBeGreaterThan(0);
    await expect(canvas.getByText(/수정된 이유/)).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '승인' }));
    await expect(args.onApprove).toHaveBeenCalledWith(modifiedEntry.id);
    await userEvent.click(canvas.getByRole('button', { name: '반려' }));
    await expect(args.onReject).toHaveBeenCalledWith(modifiedEntry.id);
    // 개별 블록 수정은 범위 밖이라 진입점이 없어야 한다 — 죽은 버튼을 남기지 않는다.
    await expect(canvas.queryByRole('button', { name: /수정/ })).toBeNull();

    // 헤더 액션은 셰브런·반려·승인 셋뿐이다.
    const names = canvas.getAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent);
    await expect(names).toEqual(['접기', '반려', '승인']);
  },
};

export const Added: Story = {
  args: { entry: addedEntry },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('PG 점검 시간 예외')).toBeInTheDocument();
    // 산문 없는 블록(옛 데이터)은 body로 폴백한다
    await expect(canvasElement.textContent).toContain('PG사 정기 점검 시간에는 재시도를 수행하지 않는다.');
    // 단일 전폭 패널 — 빨강(before) 패널이 없어야 한다
    await expect(canvasElement.querySelectorAll('[class*="border-red"]')).toHaveLength(0);
  },
};

/** 빠진 블록. 판정 경로가 없어 섹션이 canReview=false로 내려보낸다 — 열람만 남는다. */
export const Removed: Story = {
  args: { entry: removedEntry, canReview: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('수동 재시도 안내')).toBeInTheDocument();

    // 보낼 수 없는 요청의 버튼을 남기지 않는다 — 셰브런만 버튼이다
    const names = canvas.getAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent);
    await expect(names).toEqual(['접기']);
    // 초록(after) 패널이 없어야 한다
    await expect(canvasElement.querySelectorAll('[class*="border-green"]')).toHaveLength(0);
    // 색만으로 삭제를 알리지 않는다 — 고지 문구가 패널 안에 있어야 한다.
    await expect(canvas.getByText('콘텐츠를 삭제함')).toBeInTheDocument();
    // 빠진 블록은 변경안에 자리가 없어 사유가 실릴 곳도 판정 경로도 없다.
    await expect(canvas.queryByText(/수정된 이유/)).toBeNull();
  },
};

/** 반려 사유 입력 자리가 없을 때 — 반려 버튼이 사라지고 승인만 남는다. */
export const NoRejectPath: Story = {
  args: { entry: modifiedEntry, canReject: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const names = canvas.getAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent);
    await expect(names).toEqual(['접기', '승인']);
  },
};

/** 반려 처리된 블록. 액션 버튼이 사라지고 "반려됨" 배지만 남으며, 펼치면 반려 사유가 있다. */
export const Rejected: Story = {
  args: {
    entry: { ...modifiedEntry, rejected: true, rejectionReason: REJECTION_REASON },
    defaultCollapsed: true,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('반려됨')).toBeInTheDocument();
    // 판정이 끝났으므로 액션이 하나도 남으면 안 된다 — 셰브런만 버튼이다
    const names = canvas.getAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent);
    await expect(names).toEqual(['펼치기']);

    // 검토자가 적은 사유가 읽을 자리를 갖는다 — "수정된 이유"와 같은 패널이다
    await userEvent.click(canvas.getByRole('button', { name: '펼치기' }));
    await expect(canvas.getByText('반려 사유')).toBeInTheDocument();
    await expect(canvas.getByText(REJECTION_REASON)).toBeInTheDocument();
  },
};

/**
 * 승인 처리된 블록. 액션이 빠지고 접힌 채로 남는다 —
 * 반려됨에 해당하는 "승인됨" 배지는 시안에 없어 접힘 자체가 유일한 표시다.
 */
export const Approved: Story = {
  args: { entry: { ...modifiedEntry, approved: true }, defaultCollapsed: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 판정이 끝났으므로 액션이 하나도 남으면 안 된다 — 셰브런만 버튼이다
    const names = canvas.getAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent);
    await expect(names).toEqual(['펼치기']);

    // 승인에는 대응 배지가 없다
    await expect(canvas.queryByText(/승인됨|반려됨/)).toBeNull();

    // 열람은 그대로다 — 펼치면 본문이 돌아온다
    await userEvent.click(canvas.getByRole('button', { name: '펼치기' }));
    await expect(canvasElement.textContent).toContain('세 번까지');
  },
};

export const Collapsed: Story = {
  args: { entry: modifiedEntry, defaultCollapsed: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 접힌 상태 — 본문과 푸터가 없다
    await expect(canvasElement.textContent).not.toContain('세 번까지');
    await expect(canvas.queryByText(/수정된 이유/)).toBeNull();

    // 셰브런으로 펼치면 본문이 돌아온다
    await userEvent.click(canvas.getByRole('button', { name: '펼치기' }));
    await expect(canvasElement.textContent).toContain('세 번까지');
  },
};

export const LongText: Story = {
  args: { entry: longEntry },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('고객 안내 문구 표준')).toBeInTheDocument();
    // 긴 문단은 잘리지 않고 감긴다 — 가로 스크롤이 없어야 한다
    const card = canvasElement.querySelector('section')!;
    await expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth);
  },
};

/** 검토 권한 없음 — 판정 버튼이 사라지고 diff 열람만 남는다. */
export const NoReviewPermission: Story = {
  args: { entry: modifiedEntry, canReview: false },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 결정 계열 버튼이 하나도 없다 — 남은 버튼은 접기 셰브런뿐이다
    const names = canvas.getAllByRole('button').map((b) => b.getAttribute('aria-label') ?? b.textContent);
    await expect(names).toEqual(['접기']);

    // 열람은 권한과 무관하다 — 본문과 근거가 그대로 보인다
    await expect(canvasElement.textContent).toContain('세 번까지');
    await expect(canvas.getByText(/수정된 이유/)).toBeInTheDocument();
  },
};

export const NoReason: Story = {
  args: { entry: { ...modifiedEntry, reason: null } },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.queryByText(/수정된 이유/)).toBeNull();
  },
};
