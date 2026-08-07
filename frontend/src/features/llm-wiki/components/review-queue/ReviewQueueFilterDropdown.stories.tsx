import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import IconCalendarClock from '@/public/icons/icon/calendar_clock.svg';
import IconCloudCheck from '@/public/icons/icon/cloud_check.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ReviewQueueFilterDropdown, { type ReviewQueueFilterSection } from './ReviewQueueFilterDropdown';

/**
 * 필터 축과 옵션은 전부 fixture다 — 컴포넌트는 축 목록을 알지 못한다.
 * 축 순서·아이콘은 8/7 Figma 실측(17762:105379 카드 3축 + 17762:105382 신뢰도)을 그대로 옮겼다.
 * 옵션 목록은 Figma에 없다(서브메뉴 `Show submenu: false`) — 스토리 전용 표본이다.
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
      { id: 'u-rogan', label: '팀원G' },
    ],
  },
  {
    id: 'waiting',
    label: '대기 기간',
    Icon: IconCalendarClock,
    options: [
      { id: 'over-1d', label: '1일 이상' },
      { id: 'over-3d', label: '3일 이상' },
    ],
  },
  {
    id: 'confidence',
    label: '신뢰도',
    Icon: IconCloudCheck,
    options: [
      { id: 'low', label: '낮은 순' },
      { id: 'high', label: '높은 순' },
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
      states: ['closed', 'open', 'submenu-open', 'long-label-truncation'],
      reuseNotes: [
        '공용 래퍼 `shared/components/ui/dropdown-menu`만 쓴다(@radix-ui 직접 import 금지). 서브메뉴 구성은 UserModal의 "화면 모드" 서브메뉴 관례를 그대로 따랐다 — 좌측 아이콘 + flex-1 라벨 + arrow_right.',
        'arrow_right.svg(mask0_22_331 = icon/arrow_right 22:331)·calendar_clock.svg(mask0_411_2015 = 411:2015)·cloud_check.svg(mask0_695_4940 = 695:4940)는 컴포넌트 id가 리포 에셋과 정확히 일치한다. wiki_channel.svg는 DashboardDocumentRow, person.svg는 UserModal이 이미 쓰는 에셋이다. 신규 export 없음.',
        '트리거 시각(36 정사각·radius/lg·Line/Normal/Neutral 테두리·Fill/Normal/Normal 배경)은 공용 `filter-dropdown.tsx` 트리거와 같은 DS Icon button(392:1887, Outline(Gray)/medium) 계열이라 그 클래스 조합을 계승했다. 공용 IconButton 컴포넌트는 리포에 아직 없다.',
      ],
      dataNotes: [
        '8/7 재확인: 필터 카드(17762:105379)는 대상 채널·담당자·대기 기간 3개이고 신뢰도(17762:105382)는 카드 밖에 낱개로 놓여 있다. 4축 모두 존재하지만 신뢰도의 카드 내 위치는 UNKNOWN이라 fixture에서 마지막에 뒀다 — 축·순서는 props라 코드 변경 없이 바뀐다.',
        '신뢰도는 필터 축으로는 FOUND다. 행 표시(ReviewQueueRow)만 MISSING이므로 여기서 지우면 안 된다.',
        '각 축의 옵션 목록은 Figma에 없다 — 항목의 `submenu` 속성이 `Show submenu: false`다. 서브메뉴가 열린 화면이 없어서 옵션은 컴포넌트가 아니라 fixture가 정한다.',
        '"결과 없음"·로딩 스토리는 만들지 않는다(감사 금지 목록). 옵션 0개 축도 Figma 근거가 없어 다루지 않는다.',
        '유형·상태 드롭다운(17762:105231·17762:105241)은 같은 툴바에 있지만 별개의 outline 칩 컨트롤이라(Dropdown 665:14237) 이 컴포넌트가 아니다.',
      ],
      tokenNotes: [
        '카드: Fill/Normal/Normal #FFFFFF, Line/Normal/Normal #E1E2E4 = border-line-normal-normal(래퍼 기본값과 일치), padding 6/8 = px-1.5 py-2(래퍼 기본값과 일치), Shadow/Dropdown menu = shadow-dropdown-menu.',
        '항목: radius/lg 8 = rounded-lg, padding/8 = p-2, 아이콘-라벨 gap/10 = gap-2.5, 라벨-화살표 gap/4 = gap-1. 라벨은 body(md)/small = text-body-small, Text/Normal/Normal #33363D = text-text-normal-normal.',
        '좌측 아이콘 Icon/Normal/Normal #464C53 = text-icon-normal-normal, 화살표 Icon/Normal/Alternative #B1B8BE = text-icon-normal-alternative, 트리거 아이콘 Icon/Normal/Neutral #6D7882 = text-icon-normal-neutral.',
        '하이라이트 채움은 Figma가 Fill/Normal/interaction/Hover #1E212 40F(알파 6%)인데 코드 토큰은 아직 불투명 구버전이다 — 공용 래퍼가 이미 `data-[highlighted]:bg-fill-normal-interaction-hover`를 쓰므로 여기서 손대지 않았다(토큰 마이그레이션 대상).',
      ],
      layoutNotes: [
        '카드 폭 200은 Figma가 fixed로 못박은 값이라 `w-50`으로 고정했다(래퍼 기본은 min-w-50뿐이라 긴 라벨에서 늘어난다). 폭이 고정이므로 라벨은 truncate로 흡수한다 — LongLabelTruncation이 이걸 지킨다.',
        '항목 높이 40은 결과값이다(padding 8 + 아이콘 24 + 8). h-*를 두지 않았다.',
        '고정 치수는 트리거 36(컨트롤)·아이콘 24·카드 폭 200 세 개뿐이다.',
        '항목 레벨의 폭 흡수 슬롯은 라벨 하나다 — 아이콘·화살표는 shrink-0.',
        '서브메뉴 폭은 Figma 근거가 없어 래퍼 기본(min-w-50)을 그대로 뒀다.',
      ],
      interactionNotes: [
        '축은 서브메뉴 트리거다 — Figma 항목마다 icon/arrow_right가 켜져 있고(`Show icon/arrow_right: true`) 평면 목록 라벨·구분선은 없다. 그래서 DropdownMenuLabel/Separator가 아니라 Sub/SubTrigger/SubContent를 쓴다.',
        '트리거 hover/pressed는 Figma 노드에 정의가 없다. 공용 filter-dropdown.tsx 트리거의 기존 조합을 계승한 것이고, 새로 발명한 시각 상태가 아니다.',
        '드롭다운은 포털로 렌더되므로 play는 `canvasElement.ownerDocument.body` 스코프로 찾는다.',
      ],
    }),
  },
} satisfies Meta<typeof ReviewQueueFilterDropdown>;

export default meta;
type Story = StoryObj<typeof ReviewQueueFilterDropdown>;

/** 닫힌 상태. 툴바(17762:105221) 우측의 filter_list 아이콘 버튼만 보인다. */
export const Default: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    const trigger = canvas.getByRole('button', { name: '필터' });
    // 아이콘 버튼 36×36(Icon button 392:1886). 라벨 텍스트가 있으면 폭이 어긋난다.
    const box = trigger.getBoundingClientRect();
    await expect(box.width).toBe(36);
    await expect(box.height).toBe(36);
    await expect(trigger).toHaveTextContent('');

    // 닫힌 상태에서 축이 새어나오면 안 된다.
    await expect(body.queryByText('대상 채널')).toBeNull();
  },
};

/** 열린 메뉴(17762:105379). 축 4개가 서브메뉴 트리거로 놓인다. */
export const Open: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '필터' }));

    await expect(await body.findByText('대상 채널')).toBeInTheDocument();
    await expect(body.getByText('담당자')).toBeInTheDocument();
    await expect(body.getByText('대기 기간')).toBeInTheDocument();
    // 신뢰도는 필터 축으로는 FOUND다 — 행에서 뺐다고 여기서도 빠지면 안 된다.
    await expect(body.getByText('신뢰도')).toBeInTheDocument();

    // 축은 서브메뉴 트리거다. 열기 전에는 옵션이 보이면 안 된다(평면 목록으로 펼쳐졌다는 뜻).
    await expect(body.queryByText('결제')).toBeNull();
    await expect(body.queryByText('3일 이상')).toBeNull();

    // Figma가 fixed 200으로 못박은 카드 폭. 열림 애니메이션(zoom-in-95)이 transform을 걸어
    // getBoundingClientRect는 재는 시점에 따라 197 같은 값이 나온다 — 레이아웃 폭으로 잰다.
    await expect(window.getComputedStyle(body.getByRole('menu')).width).toBe('200px');
  },
};

/** 축 → 서브메뉴 → 옵션 선택. 옵션은 fixture가 정하고 컴포넌트는 (축 id, 옵션 id)만 올려보낸다. */
export const SubmenuSelect: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '필터' }));
    await userEvent.click(await body.findByText('대상 채널'));

    await expect(await body.findByText('결제')).toBeInTheDocument();
    await userEvent.click(body.getByText('환불'));

    await expect(args.onSelect).toHaveBeenCalledWith('target-channel', 'ch-refund');
  },
};

/**
 * 카드 폭이 200으로 고정이라 긴 축 이름은 잘려야 한다. 감기면 항목 높이 40이 무너진다.
 * 새 디자인 상태가 아니라 Open 상태를 긴 라벨로 다시 잰 것이다.
 */
export const LongLabelTruncation: Story = {
  args: {
    sections: [
      {
        id: 'target-channel',
        label: '대상 채널 (연동된 외부 채널 전체에서 고르기)',
        Icon: IconWikiChannel,
        options: [{ id: 'ch-billing', label: '결제' }],
      },
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '필터' }));
    const label = await body.findByText('대상 채널 (연동된 외부 채널 전체에서 고르기)');

    // 긴 라벨이 카드를 늘리면 안 된다(래퍼 기본 min-w-50만으로는 늘어난다).
    await expect(window.getComputedStyle(body.getByRole('menu')).width).toBe('200px');
    await expect(label.scrollWidth).toBeGreaterThan(label.clientWidth);
    await expect(label.getClientRects()).toHaveLength(1);
  },
};
