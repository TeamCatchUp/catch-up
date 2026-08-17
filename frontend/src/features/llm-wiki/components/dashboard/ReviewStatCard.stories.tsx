import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { REVIEW_STAT_CARD_FIXTURES } from '../../fixtures/llmWikiFixtures';
import ReviewStatCard from './ReviewStatCard';

/** 라벨 span → 텍스트 열 → 카드 루트 순으로 거슬러 올라간다. */
const cardOf = (label: HTMLElement) => label.parentElement!.parentElement!;

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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18207-128667',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18207:128667',
      },
      viewport: { width: 1040, height: 120 },
      states: ['default', 'all-metrics', 'unknown-id'],
      dataNotes: [
        '수치 로딩·집계 실패 상태 스토리는 만들지 않는다 — 디자인 MISSING.',
        '2026-08-14 확정: 지표 4종(검토 대기·내 담당·담당자 미지정·전체 위키). 8/13 시점의 중복 "검토 대기" 카드가 사라지고 "전체 위키"가 들어오면서 지표 수 질문(#26)이 해소됐다. 구 4종(미해결 충돌·태그 미분류·장기 미변경)은 8/13에 이미 소멸.',
        '"전체 위키"는 필터가 아니라 해제다 — 누르면 표가 원래대로 돌아온다(dashboardFilters가 그 계약을 갖고 unit이 지킨다).',
        '미지 stat id는 일러스트를 발명하지 않고 회색 패널만 남긴다 — UnknownId 스토리가 가드.',
      ],
      tokenNotes: [
        '카드: 테두리 #EAEBEC = border-line-normal-neutral, radius 12 = rounded-xl, 그림자 없음(구 shadow-card 제거). 4색 톤 배경 체계는 8/13 시안에서 소멸.',
        '라벨 #6D7882 = text-text-normal-alternative + body(md)/small, 수치 #33363D = text-text-normal-normal + heading(sb)/xlarge. 두 토큰 모두 weight 포함이라 font-* 불필요.',
        '일러스트 패널 #F7F7F8 = bg-fill-normal-strong — SVG가 같은 배경을 품고 있어 패널 배경은 여백 메움용.',
      ],
      layoutNotes: [
        '텍스트 열 px-5 py-4, 라벨→수치 순서(구 시안의 반대), 사이 gap 2 = gap-0.5. 높이 89는 결과값(16+23+2+32+16)이라 h-* 금지.',
        '우측 패널 폭 100 = w-25 고정(일러스트 원본 100×89, 컨트롤 아닌 장식이지만 시안이 fixed) + self-stretch.',
        '카드 폭 무고정 — 1040 행 = 245×4 + 20×3(8/14 실측, 구 248/16에서 갱신). 슬롯이 폭을 준다.',
        '라벨·수치 truncate는 좁은 슬롯의 안전 기본값이다(시안은 nowrap만 정의) — 디자이너 제안 사항.',
      ],
      reuseNotes: [
        '일러스트 4종은 시안 프레임(100×89)을 SVG 그대로 내려 커밋했다 — 임의 제작 아님. 8/14에 my_assigned·unassigned가 교체되고 all_wiki가 신설됐다.',
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
    const label = canvas.getByText('검토 대기');
    const count = canvas.getByText('7');
    const card = cardOf(label);

    // 라벨이 수치보다 위다 — 구 시안과 순서가 반대라 못박는다.
    await expect(label.compareDocumentPosition(count) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    await expect(getComputedStyle(card).borderRadius).toBe('12px');
    await expect(card.getBoundingClientRect().width).toBe(480);

    // 우측 일러스트 패널은 유일한 고정폭(100)이고, 알려진 지표라 SVG가 실린다.
    const panel = card.lastElementChild as HTMLElement;
    await expect(panel.getBoundingClientRect().width).toBe(100);
    await expect(panel.querySelector('svg')).not.toBeNull();
  },
};

export const AllMetrics: Story = {
  args: { stat: REVIEW_STAT_CARD_FIXTURES[0] },
  render: () => (
    <div className="grid w-260 grid-cols-4 gap-5">
      {REVIEW_STAT_CARD_FIXTURES.map((stat) => (
        <ReviewStatCard key={stat.id} stat={stat} />
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const cards = REVIEW_STAT_CARD_FIXTURES.map((stat) => cardOf(canvas.getByText(stat.label)));
    await expect(cards).toHaveLength(4);

    // 지표 매핑이 무너지면 일러스트가 조용히 빠진다 — 카드마다 정확히 1개씩 실리는지 센다.
    for (const card of cards) {
      await expect(card.querySelectorAll('svg')).toHaveLength(1);
    }

    // 일러스트는 지표마다 다른 에셋이다 — 같은 그림이 두 번 실리면 매핑이 어긋난 것이다.
    const drawings = cards.map((card) => card.querySelector('svg')?.innerHTML);
    await expect(new Set(drawings).size).toBe(4);
  },
};

/** 미지 지표 id. 새 그림·새 색을 발명하지 않고 회색 패널만 남는다. */
export const UnknownId: Story = {
  args: { stat: { id: 'stat-not-yet-known', label: '신규 지표', count: 3 } },
  render: (args) => (
    <div className="w-120">
      <ReviewStatCard {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const card = cardOf(canvas.getByText('신규 지표'));

    const panel = card.lastElementChild as HTMLElement;
    await expect(panel.getBoundingClientRect().width).toBe(100);
    await expect(panel.querySelector('svg')).toBeNull();
  },
};
