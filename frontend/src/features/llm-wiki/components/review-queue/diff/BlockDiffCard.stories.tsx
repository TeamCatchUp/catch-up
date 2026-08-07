import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import {
  BASE_WIKI_BLOCKS,
  LONG_BASE_WIKI_BLOCKS,
  LONG_PROPOSED_WIKI_BLOCKS,
  PROPOSED_WIKI_BLOCKS,
} from '../../../fixtures/llmWikiDiffFixtures';
import { computeBlockDiff } from '../../../utils/diff/computeBlockDiff';
import BlockDiffCard from './BlockDiffCard';

const entries = computeBlockDiff(BASE_WIKI_BLOCKS, PROPOSED_WIKI_BLOCKS);
const modifiedEntry = entries.find((e) => e.kind === 'modified')!;
const addedEntry = entries.find((e) => e.kind === 'added')!;
const removedEntry = entries.find((e) => e.kind === 'removed')!;
const [longEntry] = computeBlockDiff(LONG_BASE_WIKI_BLOCKS, LONG_PROPOSED_WIKI_BLOCKS);

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/BlockDiffCard',
  component: BlockDiffCard,
  tags: ['autodocs'],
  args: { onApprove: fn(), onRevert: fn(), onDelete: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17848-106171',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17848:106171',
      },
      viewport: { width: 700, height: 420 },
      states: ['modified', 'added', 'removed', 'collapsed', 'long-text', 'no-reason'],
      reuseNotes: [
        '버튼은 공용 Button(box-solid-primary/box-outline-gray/icon-only-gray)을 그대로 쓴다 — 시안의 Box Button small(30px)·Icon button small(28px) 대응.',
        '시안의 연필·순환화살표 아이콘과 카드 직접 수정 버튼은 렌더하지 않는다 — 순환화살표는 되돌리기 중복, 블록 단위 편집 진입은 디자인 미정으로 추후 작업(2026-08-07 사용자 확정). 카드 버튼은 삭제·되돌리기·승인 3종.',
      ],
      dataNotes: [
        '엔트리는 픽스처 blocks[] 쌍에 computeBlockDiff를 돌려 얻는다 — 계산과 표시가 같은 파이프라인을 지나는 것을 스토리가 상시 검증한다.',
        'removed 카드(빨강 단일 전폭)는 시안에 없는 프론트 잠정안이다 — added(초록 단일 전폭)의 거울상. design-request 9번으로 확인 요청 상태.',
        '카드 제목·"수정된 이유"의 실카피는 시안이 placeholder라 미정(감사 UNKNOWN 카피 미정). 빈 diff·로딩·에러 스토리는 만들지 않는다(MISSING).',
      ],
      tokenNotes: [
        '패널 색은 8/7 실측 확정 — removed: bg-red-1(#FFFAFA)/바 red-40/호버 red-5, added: bg-green-5(#E6FAF2)/바 green-60(#00985A)/호버 green-10. 감사 §9 부록 참조.',
        '단어 강조(red-10/green-20)만 시안에 없는 프론트 결정 — design-request 10번으로 디자이너 확인 대기.',
        '카드 테두리 #EAEBEC=border-line-normal-neutral·radius 12=rounded-xl. 수정된 이유 바(17849:106254, 8/7 개정): 세로 배치 gap 8 — 레이블 #6D7882=text-text-normal-alternative body-xsmall + 본문 #464C53=text-text-normal-neutral body-small, 배경 #F7F7F8=bg-fill-normal-strong.',
      ],
      interactionNotes: [
        '줄 호버 하이라이트는 패널별 독립이고 클릭 동작이 없다(시안 우측 첫 행 진한 초록 #D9F7EB = 호버 상태, 2026-08-07 확인).',
        '접기는 uncontrolled — 셰브런이 본문·수정된 이유를 함께 숨긴다.',
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
    // 좌우 패널이 모두 있고, 바뀐 단어가 양쪽에서 강조된다
    await expect(canvas.getByText('1회')).toBeInTheDocument();
    await expect(canvas.getByText('3회까지')).toBeInTheDocument();
    await expect(canvas.getByText(/수정된 이유/)).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '승인' }));
    await expect(args.onApprove).toHaveBeenCalledWith(modifiedEntry.id);
    await userEvent.click(canvas.getByRole('button', { name: '되돌리기' }));
    await expect(args.onRevert).toHaveBeenCalledWith(modifiedEntry.id);
    await userEvent.click(canvas.getByRole('button', { name: '삭제' }));
    await expect(args.onDelete).toHaveBeenCalledWith(modifiedEntry.id);

    // 카드에는 직접 수정 버튼이 없다 — 섹션 헤더에만 있다(2026-08-07 사용자 결정)
    await expect(canvas.queryByRole('button', { name: '직접 수정' })).toBeNull();
  },
};

export const Added: Story = {
  args: { entry: addedEntry },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('PG 점검 시간 예외')).toBeInTheDocument();
    // 단일 전폭 패널 — 빨강(before) 패널이 없어야 한다
    await expect(canvasElement.querySelectorAll('[class*="border-red"]')).toHaveLength(0);
  },
};

export const Removed: Story = {
  args: { entry: removedEntry },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('수동 재시도 안내')).toBeInTheDocument();
    // added의 거울상 — 초록(after) 패널이 없어야 한다
    await expect(canvasElement.querySelectorAll('[class*="border-green"]')).toHaveLength(0);
    // removed는 reason이 없다 — 푸터 바가 렌더되지 않는다
    await expect(canvas.queryByText(/수정된 이유/)).toBeNull();
  },
};

export const Collapsed: Story = {
  args: { entry: modifiedEntry, defaultCollapsed: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 접힌 상태 — 본문과 푸터가 없다
    await expect(canvas.queryByText('1회')).toBeNull();
    await expect(canvas.queryByText(/수정된 이유/)).toBeNull();

    // 셰브런으로 펼치면 본문이 돌아온다
    await userEvent.click(canvas.getByRole('button', { name: '펼치기' }));
    await expect(canvas.getByText('1회')).toBeInTheDocument();
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

export const NoReason: Story = {
  args: { entry: { ...modifiedEntry, reason: null } },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.queryByText(/수정된 이유/)).toBeNull();
  },
};
