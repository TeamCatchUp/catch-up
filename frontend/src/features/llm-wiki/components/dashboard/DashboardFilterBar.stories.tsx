import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import DashboardFilterBar from './DashboardFilterBar';

const meta = {
  title: 'Compositions/LLM Wiki/Dashboard/DashboardFilterBar',
  component: DashboardFilterBar,
  tags: ['autodocs'],
  args: {
    sortLabel: '최근 변경 순',
    onSearchChange: fn(),
    onFilterClick: fn(),
    onSortClick: fn(),
    onClearFilters: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17681-153545',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17681:153545',
      },
      viewport: { width: 1040, height: 168 },
      states: ['default', 'narrow-slot'],
      reuseNotes: [
        '필터 칩은 shared Chip(variant=square)이다 — 미선택 토큰(흰 배경·Line/Normal/Neutral·Text/Normal/Normal)과 선택 토큰(Fill/Primary/Normal/Assistive·Line/Primary/Normal·Text/Primary/Normal)이 시안과 그대로 일치해 새 칩을 만들지 않았다. 시안 gap 8·padding 10만 className으로 덮는다.',
        '검색창만 직접 조립했다 — 공용 Input에 아이콘 슬롯이 없고, 시안 배경(Fill/Normal/Strong)·테두리(Line/Normal/Assistive)가 Input의 두 size 어느 쪽과도 다르다.',
        'align·progress·calendar·person·search_300·cancel_small·dropdown_down 전부 기존 에셋이고 Figma 컴포넌트명과 1:1 — 신규 export 없음.',
      ],
      dataNotes: [
        '축 3종(담당자·상태·생성일)은 시안 실재분으로 컴포넌트가 들고 있다 — 화면 하나에만 쓰이고 시안이 고정한 목록이라 props로 열지 않았다. 늘어나면 그때 연다.',
        '칩의 드롭다운 메뉴는 시안에 없다 — 트리거까지만 구현하고 콜백만 올려보낸다(ReviewQueueFilterDropdown이 8/7에 같은 방식으로 처리한 선례).',
        '검색 결과·필터 적용 결과는 이 컴포넌트의 관심사가 아니다 — 입력만 올려보내고 목록은 페이지가 갖는다.',
      ],
      tokenNotes: [
        '바 컨테이너: 배경 Fill/Normal/Assistive(흰색) + Line/Normal/Neutral 테두리 + radius 12 + padding 20 + gap 12.',
        '검색창: Fill/Normal/Strong 배경 + Line/Normal/Assistive 1px 테두리 + radius 8 + px 12 py 8, min-h 40. placeholder Text/Normal/Assistive.',
        '칩: h 36 + radius 8 + px 10 + gap 8, 아이콘 20. 정렬 칩만 선택 톤이다.',
        '필터 초기화: heading(sb)/small + Text/Normal/Alternative, 아이콘 cancel_small 20 + gap 6, h 36.',
      ],
      layoutNotes: [
        '폭을 갖지 않는다 — 1040은 대시보드 콘텐츠 열의 값이고 슬롯이 준다.',
        '폭 흡수는 칩 묶음 하나다(min-w-0 flex-1). 초기화 버튼은 shrink-0이라 좁아져도 밀리지 않는다.',
        '칩 상한 180(max-w-45)·하한 36(min-w-9)은 시안 고정값이고, 긴 정렬 라벨은 그 안에서 잘린다.',
      ],
    }),
  },
} satisfies Meta<typeof DashboardFilterBar>;

export default meta;
type Story = StoryObj<typeof DashboardFilterBar>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByPlaceholderText('검색어를 입력하세요.')).toBeInTheDocument();

    const assigneeChip = canvas.getByRole('button', { name: /담당자/ });
    const sortChip = canvas.getByRole('button', { name: /최근 변경 순/ });

    // 축 3종 + 정렬 1종 = 칩 4개, 그 밖에 초기화 버튼 1개.
    await expect(canvas.getAllByRole('button')).toHaveLength(5);
    await expect(assigneeChip.getBoundingClientRect().height).toBe(36);

    // 정렬 칩만 선택 톤이다 — 나머지와 배경·테두리가 갈려야 한다.
    await expect(sortChip).toHaveAttribute('data-selected', 'true');
    await expect(assigneeChip).toHaveAttribute('data-selected', 'false');
    await expect(getComputedStyle(sortChip).backgroundColor).not.toBe(getComputedStyle(assigneeChip).backgroundColor);

    await userEvent.click(assigneeChip);
    await expect(args.onFilterClick).toHaveBeenCalledWith('assignee');

    await userEvent.click(sortChip);
    await expect(args.onSortClick).toHaveBeenCalled();

    await userEvent.type(canvas.getByPlaceholderText('검색어를 입력하세요.'), '결제');
    await expect(args.onSearchChange).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: /필터 초기화/ }));
    await expect(args.onClearFilters).toHaveBeenCalled();
  },
};

/** 좁은 슬롯. 칩 묶음이 줄고 초기화 버튼은 밀리지 않아야 한다. */
export const NarrowSlot: Story = {
  args: { sortLabel: '최근 변경 순으로 아주 길게 정렬하기' },
  decorators: [
    (Story) => (
      <div className="w-160 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const slot = canvasElement.querySelector('div.w-160') as HTMLElement;

    // 바가 슬롯을 넘지 않는다.
    await expect(slot.scrollWidth).toBeLessThanOrEqual(slot.clientWidth);

    // 긴 정렬 라벨은 칩 상한 180 안에서 잘린다.
    const sortChip = canvas.getByRole('button', { name: /최근 변경 순으로/ });
    await expect(sortChip.getBoundingClientRect().width).toBeLessThanOrEqual(180);

    // 초기화 버튼은 좁아져도 온전히 남는다.
    await expect(canvas.getByRole('button', { name: /필터 초기화/ })).toBeVisible();
  },
};
