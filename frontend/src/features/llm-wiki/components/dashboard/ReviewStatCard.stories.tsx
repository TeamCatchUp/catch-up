import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { REVIEW_STAT_CARD_FIXTURES } from '../../fixtures/llmWikiFixtures';
import ReviewStatCard from './ReviewStatCard';

const meta = {
  title: 'Compositions/LLM Wiki/Dashboard/ReviewStatCard',
  component: ReviewStatCard,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17600-149361',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17600:149361',
      },
      viewport: { width: 1040, height: 120 },
      states: ['default', 'all-variants'],
      dataNotes: [
        '수치 로딩·집계 실패 상태 스토리는 만들지 않는다 — 디자인 MISSING.',
        '4종(검토 대기·미해결 충돌·태그 미분류·장기 미변경 문서)은 2026-08-06 Figma 재확인에서 그대로 유지됐다.',
      ],
      tokenNotes: [
        '카드는 톤별로 배경·글자색이 다르다: 검토 대기 #F0ECFE/#6541F2 = bg-accent-violet-neutral·text-accent-violet-default, 미해결 충돌 #FEEEE5/#FF5E00 = bg-accent-red-orange-lighten·text-accent-red-orange-default, 장기 미변경 문서 #E7F4FE/#00AEFF = bg-accent-information-lighten·text-accent-light-blue-default.',
        '태그 미분류만 중립 톤이고 수치·라벨 색이 갈린다: #F7F7F8 = bg-fill-normal-strong, 수치 #464C53 = text-text-normal-neutral, 라벨 #6D7882 = text-text-normal-alternative.',
        'heading(sb)/xlarge = text-heading-xlarge(24/1.34/600), body(md)/small = text-body-small. 두 토큰 모두 weight를 포함하므로 font-semibold를 덧붙이지 않는다.',
        'radius 12 = rounded-xl, Shadow/card(0 0 12px rgba(111,113,115,0.03)) = shadow-card. 테두리(stroke)는 없다 — REST 노드에 strokes가 비어 있고 스크린샷 가장자리도 단색이다.',
      ],
      layoutNotes: [
        '카드는 Figma에서 horizontal fill이라 폭을 고정하지 않는다. 1040 행 = 248×4 + 16×3이므로 스토리에서만 grid-cols-4 gap-4로 그 슬롯을 재현한다.',
        '패딩 12/16 = py-3 px-4, 수치-라벨 간격 8 = gap-2. 높이 87은 결과값(12 + 32 + 8 + 23 + 12)이라 h-*로 고정하지 않는다.',
      ],
      reuseNotes: [
        '톤은 데이터에 없다. Figma가 4종 지표를 고정 색으로 못박아 stat id로 매핑하고, 미지 id는 중립 톤(태그 미분류와 동일)으로 떨어뜨린다 — 새 색을 발명하지 않기 위해서다.',
      ],
    }),
  },
} satisfies Meta<typeof ReviewStatCard>;

export default meta;
type Story = StoryObj<typeof ReviewStatCard>;

export const Default: Story = {
  args: { stat: REVIEW_STAT_CARD_FIXTURES[0] },
  // 슬롯을 시안 폭이 아닌 값으로 둬서 카드에 px 폭이 박히지 않았는지를 수치로 확인한다.
  render: (args) => (
    <div className="w-120">
      <ReviewStatCard {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('검토 대기')).toBeInTheDocument();
    await expect(canvas.getByText('12')).toBeInTheDocument();

    // 반경은 한 단계 어긋나도 눈으로 잘 안 잡히므로 못박는다.
    const card = canvas.getByText('검토 대기').parentElement!;
    await expect(getComputedStyle(card).borderRadius).toBe('12px');
    await expect(card.getBoundingClientRect().width).toBe(480);
  },
};

export const AllVariants: Story = {
  args: { stat: REVIEW_STAT_CARD_FIXTURES[0] },
  render: () => (
    <div className="grid w-260 grid-cols-4 gap-4">
      {REVIEW_STAT_CARD_FIXTURES.map((stat) => (
        <ReviewStatCard key={stat.id} stat={stat} />
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 라벨 span의 부모가 카드다. 4종이 모두 그려지는지부터 확인한다.
    const cards = REVIEW_STAT_CARD_FIXTURES.map((stat) => canvas.getByText(stat.label).parentElement!);
    await expect(cards).toHaveLength(4);

    // 톤 매핑이 무너지면 4장이 같은 회색이 된다. 특정 색을 못박으면 다크에서 깨지므로 "서로 다르다"만 본다.
    const backgrounds = cards.map((card) => getComputedStyle(card).backgroundColor);
    await expect(new Set(backgrounds).size).toBe(4);

    // 태그 미분류만 수치와 라벨 색이 갈린다. 나머지 3종은 같은 색이다.
    const neutralCard = cards[2];
    const [neutralCount, neutralLabel] = Array.from(neutralCard.children);
    await expect(getComputedStyle(neutralCount).color).not.toBe(getComputedStyle(neutralLabel).color);

    const violetCard = cards[0];
    const [violetCount, violetLabel] = Array.from(violetCard.children);
    await expect(getComputedStyle(violetCount).color).toBe(getComputedStyle(violetLabel).color);
  },
};
