import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import IconCalendarClock from '@/public/icons/icon/calendar_clock.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ReviewQueueFilterDropdown, { type ReviewQueueFilterSection } from './ReviewQueueFilterDropdown';

/**
 * 필터 축과 옵션은 전부 fixture다 — 컴포넌트는 축 목록을 알지 못한다.
 * 대기 기간 옵션 4개만 시안 실측값이고, 담당자·대상 채널 옵션은 자리 표본이다(아래 dataNotes).
 */
const SECTIONS: readonly ReviewQueueFilterSection[] = [
  {
    id: 'target-channel',
    label: '대상 채널',
    Icon: IconWikiChannel,
    options: [
      { id: 'ch-billing', label: '결제' },
      { id: 'ch-refund', label: '환불' },
    ],
  },
  {
    id: 'assignee',
    label: '담당자',
    Icon: IconPerson,
    options: [
      { id: 'u-seoyeon', label: '직원10' },
      { id: 'u-jinsu', label: '이진수' },
    ],
  },
  {
    id: 'waiting',
    label: '대기 기간',
    Icon: IconCalendarClock,
    valueLabel: '전체',
    selectedOptionId: 'all',
    options: [
      { id: 'all', label: '전체' },
      { id: 'today', label: '오늘' },
      { id: 'within-7d', label: '7일 이내' },
      { id: 'before', label: '이전' },
    ],
  },
];

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/ReviewQueueFilterDropdown',
  component: ReviewQueueFilterDropdown,
  tags: ['autodocs'],
  args: { sections: SECTIONS, onSelect: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17762-105579',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17762:105579',
      },
      viewport: { width: 360, height: 400 },
      states: ['closed', 'open', 'submenu-select', 'filtered-trigger', 'long-label-truncation'],
      reuseNotes: [
        '공용 래퍼 `shared/components/ui/dropdown-menu`만 쓴다(@radix-ui 직접 import 금지). 서브메뉴 구성은 Sub/SubTrigger/SubContent.',
        'wiki_channel·person·calendar_clock·arrow_right 에셋 재사용. filter_list_filled.svg만 신규 — 시안의 "필터링 걸려 있을 때" 글리프(408:2216)를 그대로 내리고 fill을 currentColor로 바꿨다(dash-circle 선례).',
      ],
      dataNotes: [
        '2026-08-13 재실측: 축이 4개→3개다 — 신뢰도 축이 시트(17762:105579)에서 소멸했다. 순서는 대상 채널→담당자→대기 기간.',
        '대기 기간 옵션(전체·오늘·7일 이내·이전)은 시안 실측값이다(18112:48066). 첫 항목이 지속 하이라이트 — 축 행의 현재값 "전체"와 함께 읽어 선택 상태로 판정했다(hover 목업 가능성은 interactionNotes).',
        '담당자·대상 채널의 2차 패널은 검색 입력+선택 칩+목록의 멀티셀렉트다(17762:105579 시트) — 빈 검색 결과·칩 초과·행 "PM" 라벨 의미가 전부 미정의라 구현을 이연하고 옵션 평면 목록이 자리를 지킨다. design-request 질문 등록.',
        '"결과 없음"·로딩 스토리는 만들지 않는다(감사 금지 목록).',
      ],
      tokenNotes: [
        '카드: Fill/Normal/Normal 흰 배경 + Line/Normal/Normal 테두리(래퍼 기본값), radius 12 = rounded-xl — 래퍼 기본 16(rounded-2xl)을 시안값으로 덮는다.',
        '축 행: 라벨 body(md)/small #33363D, 좌측 아이콘 24 #464C53 = text-icon-normal-normal, 화살표 24 #B1B8BE = text-icon-normal-alternative.',
        '현재값 요약: body(md)/xsmall 13 #6D7882 = text-text-normal-alternative, max-w 78 = max-w-19.5 truncate.',
        '트리거 열림: Fill/Normal/interaction/Pressed(10% 알파) + Line/Normal/Strong #DBDCDF — data-[state=open]으로 표현. 필터링 중 글리프 #0066FF = text-icon-primary-normal(currentColor 전환).',
        '항목 하이라이트·선택 채움 모두 Fill/Normal/interaction/Hover(6% 알파) = bg-fill-normal-interaction-hover.',
      ],
      layoutNotes: [
        '고정 치수: 트리거 36(컨트롤)·아이콘 24·1차 카드 폭 250(w-62.5)·옵션 카드 폭 200(w-50) — 전부 시안 fixed.',
        '항목 높이 40은 결과값(패딩 8+아이콘 24+8) — h-* 금지. 항목 레벨의 폭 흡수는 라벨 하나(min-w-0 flex-1), 현재값·아이콘·화살표는 shrink-0.',
        '1차 카드 폭이 250으로 늘며(구 200) 긴 라벨 흡수 여유가 커졌지만 truncate 계약은 유지한다.',
      ],
      interactionNotes: [
        '축은 서브메뉴 트리거다 — 시트의 2차 카드가 1차 옆에 배치되어 있고 축 행마다 arrow_right가 켜져 있다.',
        '옵션 "전체"의 지속 하이라이트는 선택 상태로 해석했다(축 행 현재값과 동반 표기). hover 목업이었다면 selectedOptionId를 안 넘기면 그만이라 계약 위험이 없다.',
        '트리거 hover는 시안에 정의가 없다 — 기존 계승 조합 유지(발명 아님). 열림 상태만 시안 실측(pressed 배경+strong 테두리).',
        '드롭다운은 포털로 렌더되므로 play는 `canvasElement.ownerDocument.body` 스코프로 찾는다.',
      ],
    }),
  },
} satisfies Meta<typeof ReviewQueueFilterDropdown>;

export default meta;
type Story = StoryObj<typeof ReviewQueueFilterDropdown>;

/** 닫힌 상태. 툴바 우측의 필터 아이콘 버튼만 보인다. */
export const Default: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const trigger = canvas.getByRole('button', { name: '필터' });
    // 아이콘 전용 버튼이라 정사각이어야 한다 — 라벨 텍스트가 있으면 폭이 어긋난다.
    const box = trigger.getBoundingClientRect();
    await expect(box.width).toBe(36);
    await expect(box.height).toBe(36);
    await expect(trigger).toHaveTextContent('');

    // 닫힌 상태에서 축이 새어나오면 안 된다.
    await expect(body.queryByText('대상 채널')).toBeNull();
  },
};

/** 열린 메뉴. 축 3개가 서브메뉴 트리거로 놓이고 대기 기간 행은 현재값을 요약한다. */
export const Open: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const trigger = canvas.getByRole('button', { name: '필터' });
    await userEvent.click(trigger);

    await expect(await body.findByText('대상 채널')).toBeInTheDocument();
    await expect(body.getByText('담당자')).toBeInTheDocument();
    await expect(body.getByText('대기 기간')).toBeInTheDocument();
    // 신뢰도 축은 8/13 시안에서 소멸했다 — 되살아나면 회귀다.
    await expect(body.queryByText('신뢰도')).toBeNull();

    // 축 행의 현재값 요약. 옵션 목록이 열리기 전에도 보인다.
    await expect(body.getByText('전체')).toBeInTheDocument();

    // 열림 상태 시각은 data-state로 걸린다.
    await expect(trigger).toHaveAttribute('data-state', 'open');

    // 열림 애니메이션이 transform을 걸어 getBoundingClientRect가 흔들린다 — 레이아웃 폭으로 잰다.
    await expect(window.getComputedStyle(body.getByRole('menu')).width).toBe('250px');
  },
};

/** 축 → 서브메뉴 → 옵션 선택. 현재 적용값은 지속 하이라이트된다. */
export const SubmenuSelect: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '필터' }));
    await userEvent.click(await body.findByText('대기 기간'));

    // "전체"는 축 행 요약에도 있어서, 옵션 쪽은 서브메뉴 스코프로 좁혀 찾는다.
    const todayItem = (await body.findByText('오늘')).closest('[role=menuitem]') as HTMLElement;
    const submenu = todayItem.closest('[role=menu]') as HTMLElement;
    const allItem = within(submenu).getByText('전체').closest('[role=menuitem]') as HTMLElement;

    // 적용된 옵션(전체)만 채움이 있다 — 미적용(오늘)과 배경이 갈려야 한다.
    await expect(getComputedStyle(allItem).backgroundColor).not.toBe(getComputedStyle(todayItem).backgroundColor);

    // 옵션 카드 폭은 200 고정이다.
    await expect(window.getComputedStyle(submenu).width).toBe('200px');

    await userEvent.click(body.getByText('오늘'));
    await expect(args.onSelect).toHaveBeenCalledWith('waiting', 'today');
  },
};

/** 필터링 중 상태. 트리거 글리프가 파란 원형(filled)으로 바뀐다. */
export const FilteredTrigger: Story = {
  args: { filtered: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = canvas.getByRole('button', { name: '필터' });

    const glyph = trigger.querySelector('svg');
    await expect(glyph).not.toBeNull();
    // filled 글리프는 primary 아이콘 토큰을 입는다 — 기본 글리프와 클래스로 갈린다.
    await expect(glyph!.getAttribute('class') ?? '').toContain('text-icon-primary-normal');
  },
};

/** 카드 폭이 고정이라 긴 축 이름은 잘려야 한다 — 감기면 항목 높이가 무너진다. */
export const LongLabelTruncation: Story = {
  args: {
    sections: [
      {
        id: 'target-channel',
        label: '대상 채널 (연동된 외부 채널 전체에서 아주 길게 고르기)',
        Icon: IconWikiChannel,
        valueLabel: '아주 길게 늘어난 현재값 요약 표본',
        options: [{ id: 'ch-billing', label: '결제' }],
      },
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '필터' }));
    const label = await body.findByText('대상 채널 (연동된 외부 채널 전체에서 아주 길게 고르기)');

    // 긴 라벨이 카드를 늘리면 안 된다 — 공용 래퍼 기본값만으로는 늘어난다.
    await expect(window.getComputedStyle(body.getByRole('menu')).width).toBe('250px');
    await expect(label.scrollWidth).toBeGreaterThan(label.clientWidth);
    await expect(label.getClientRects()).toHaveLength(1);

    // 현재값 요약도 78 상한을 지키며 잘린다.
    const value = body.getByText('아주 길게 늘어난 현재값 요약 표본');
    await expect(value.getBoundingClientRect().width).toBeLessThanOrEqual(78);
    await expect(value.scrollWidth).toBeGreaterThan(value.clientWidth);
  },
};
