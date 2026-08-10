import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import DocumentStatusBadge from './DocumentStatusBadge';

const meta = {
  title: 'Compositions/LLM Wiki/Document/DocumentStatusBadge',
  component: DocumentStatusBadge,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17698-184150',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17698:184150',
      },
      viewport: { width: 200, height: 80 },
      states: ['reviewed', 'pending-review', 'needs-review', 'unknown-status'],
      reuseNotes: [
        '색은 shared Badge의 success·violet 변형이 Figma와 그대로 일치해 재사용하고, 기하(반경·패딩·타이포·아이콘)만 규격별로 덮는다.',
        '헤더 워크스트림이 따로 만든 ReviewNeededTag를 이 컴포넌트로 흡수했다(8/10). "검토 대기"(md)와 "검토 필요"(sm)가 같은 violet + 같은 icon/dash-circle이라 컴포넌트를 가르면 매핑이 2벌로 복제된다. WikiPageHeader는 badge를 ReactNode 슬롯으로 받으므로 소비처는 이 컴포넌트 하나만 안다.',
      ],
      dataNotes: [
        'Figma 전수 조사(8/10, Component 페이지 XML 전량 스캔)로 확인된 상태는 3종이다. reviewed=검토 완료(17698:184150 외 21곳) · pending_review=검토 대기(17849:106521) · needs_review=검토 필요(17942:91620 검토큐 헤더, 17896:46635 검토큐 상세 메타 줄).',
        '미지 status 값이 오면 배지를 렌더하지 않는다 — 임의 시각화가 승인된 디자인처럼 남는 것을 막는다(발명 금지 계약).',
        'size와 status는 직교한다. 시안에 실재하는 조합은 (md, reviewed)·(md, pending_review)·(sm, needs_review) 셋뿐이고 스토리도 그 셋만 고정한다 — 나머지 조합은 렌더는 되지만 디자인 근거가 없다.',
        '세 상태 모두 백엔드 대응이 없다([SPEC]). 큐 행의 status는 제안 판정(ChangeProposalStatus)이지 문서 상태가 아니다 — 매핑은 API 협상 대상이다.',
      ],
      tokenNotes: [
        'reviewed: 배경 #D9F7EB = bg-accent-green-neutral, 글자 #00985A = text-accent-green-default.',
        'pending_review·needs_review: 배경 #F0ECFE = bg-accent-violet-neutral, 글자·아이콘 #6541F2 = text-accent-violet-default.',
        'md 규격 = radius/lg 8(rounded-lg) · padding 4/8(py-1 px-2) · gap 8(gap-2) · body(md)/small(text-body-small) · 아이콘 20(size-5).',
        'sm 규격 = radius/md2 6(rounded-md2) · padding 2/6(py-0.5 px-1.5) · gap 4(gap-1) · body(md)/xsmall(text-body-xsmall) · 아이콘 18(size-4.5).',
        'icon/verified·icon/dash-circle 둘 다 Figma export를 currentColor로 정규화해 Badge 글자색을 상속한다 — 다크 모드에서 accent 색이 바뀌어도 따라간다.',
      ],
      layoutNotes: [
        'Figma 배지 프레임(17698:184150)은 100×31 고정이지만 라벨 길이에 따라 늘어나는 hug 성격이라 폭을 고정하지 않는다. 높이 31 = py 4 + 라인박스 22.5 + py 4.',
        'md 가로 구성 8(pl) + 20(icon) + 8(gap) + 56(text) + 8(pr) = 100 — 프레임 폭과 정확히 일치하므로 hug이 맞다.',
        'sm 가로 구성 6(pl) + 18(icon) + 4(gap) + 49(text) + 6(pr) = 83 — 태그 인스턴스(17942:91620) 폭과 일치한다. 높이 24 = py 2 + 라인박스 20 + py 2.',
      ],
    }),
  },
} satisfies Meta<typeof DocumentStatusBadge>;

export default meta;
type Story = StoryObj<typeof DocumentStatusBadge>;

/** 표 상태 열 — 검토 완료 (17698:184150) */
export const Reviewed: Story = {
  args: { status: 'reviewed' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const badge = canvas.getByText('검토 완료');
    await expect(badge).toBeInTheDocument();

    // shared Badge 기본값은 rounded-full이다. tailwind-merge가 이 덮어쓰기를 놓치면
    // 알약 모양으로 조용히 되돌아가므로 Figma의 radius/lg(8px)를 직접 못박는다.
    await expect(getComputedStyle(badge).borderRadius).toBe('8px');

    // Figma 배지는 icon/verified를 동반한다. aria-hidden이라 접근성 트리에 없으므로 DOM으로 확인한다.
    const icon = badge.querySelector('svg');
    await expect(icon).not.toBeNull();
    await expect(icon).toHaveAttribute('aria-hidden');
    await expect(icon!.getBoundingClientRect().width).toBe(20);
    // Figma export 원본은 fill="#00985A"였다. 재export로 hex가 되살아나면 라이트 모드에서는
    // 값이 우연히 같아 눈에 띄지 않고 다크 모드에서만 어긋나므로, 계산된 색이 아니라 속성을 못박는다.
    await expect(icon!.querySelector('path')).toHaveAttribute('fill', 'currentColor');
  },
};

/** 표 상태 열 — 검토 대기 (17849:106521). 같은 md 규격에서 색·아이콘만 갈린다 */
export const PendingReview: Story = {
  args: { status: 'pending_review' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const badge = canvas.getByText('검토 대기');
    await expect(badge).toBeInTheDocument();

    // reviewed와 같은 md 규격이라는 것이 이 스토리의 요점이다 — 반경이 갈리면 규격이 새어나간 것이다.
    await expect(getComputedStyle(badge).borderRadius).toBe('8px');

    const icon = badge.querySelector('svg');
    await expect(icon).not.toBeNull();
    await expect(icon!.getBoundingClientRect().width).toBe(20);
    // dash-circle은 fill이 아니라 stroke로 그려진다. 원본 export는 stroke="#464C53"이었다.
    await expect(icon!.querySelector('path')).toHaveAttribute('stroke', 'currentColor');
  },
};

/**
 * 태그 규격 — 검토 필요 (검토큐 헤더 17942:91620 · 검토큐 상세 메타 줄 17896:46635).
 * Figma 레이어명은 Tag 마스터의 기본값인 "진행중"이지만 두 인스턴스 모두 "검토 필요"로 오버라이드돼 있다.
 */
export const NeedsReviewTag: Story = {
  args: { status: 'needs_review', size: 'sm' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const tag = canvas.getByText('검토 필요');
    await expect(tag).toBeInTheDocument();

    // md와 갈리는 지점을 못박는다. sm이 md 값으로 조용히 되돌아가면 여기서 잡힌다.
    await expect(getComputedStyle(tag).borderRadius).toBe('6px');

    const icon = tag.querySelector('svg');
    await expect(icon).not.toBeNull();
    await expect(icon).toHaveAttribute('aria-hidden');
    await expect(icon!.getBoundingClientRect().width).toBe(18);
    await expect(icon!.querySelector('path')).toHaveAttribute('stroke', 'currentColor');
  },
};

/** 확정 디자인이 없는 status는 배지를 만들지 않고 아무것도 렌더하지 않는다 */
export const UnknownStatusRendersNothing: Story = {
  args: { status: 'contested' },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).queryByText(/./)).toBeNull();
  },
};

/** 규격을 못 고른 status도 마찬가지다 — sm이라고 예외가 생기지 않는다 */
export const UnknownStatusInTagSizeRendersNothing: Story = {
  args: { status: 'contested', size: 'sm' },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).queryByText(/./)).toBeNull();
  },
};
