import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { REVIEW_QUEUE_ASSIGNEE_OPTIONS } from '../../fixtures/llmWikiFixtures';
import DashboardFilterBar from './DashboardFilterBar';

const meta = {
  title: 'Compositions/LLM Wiki/Dashboard/DashboardFilterBar',
  component: DashboardFilterBar,
  tags: ['autodocs'],
  args: {
    sortId: 'recent',
    onSortSelect: fn(),
    onCreatedAtChange: fn(),
    assigneeOptions: REVIEW_QUEUE_ASSIGNEE_OPTIONS,
    selectedAssigneeIds: [],
    onAssigneeToggle: fn(),
    onStatusSelect: fn(),
    onSearchChange: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18116-58674',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18116:58674',
      },
      viewport: { width: 1040, height: 460 },
      states: [
        'default',
        'active-status',
        'status-dropdown',
        'assignee-dropdown',
        'sort-dropdown',
        'created-at-calendar',
        'narrow-slot',
      ],
      reuseNotes: [
        '필터 칩은 shared Chip(variant=square)이다 — 미선택·선택 토큰이 시안과 그대로 일치해 새 칩을 만들지 않았다. 활성 칩의 선택 톤(Fill/Primary/Normal/Assistive·Line/Primary/Normal·Text/Primary/Normal)이 시안 18183:139291과 같다.',
        '상태 드롭다운의 옵션은 DocumentStatusBadge 그 자체다 — 시안 18127:61560의 옵션이 배지(violet/green + dash-circle/verified + px8 py4 radius8)와 규격까지 같아 배지를 그대로 넣었다.',
        '담당자 드롭다운은 검토 큐의 ReviewQueueFilterSearchPanel을 그대로 쓴다 — 시안 노드(18183:137504·137516)가 검토 큐(18112:47410·47865)와 같은 구조다. 사용자 확인 완료(8/14).',
        '검색창만 직접 조립했다 — 공용 Input에 아이콘 슬롯이 없고 시안 배경·테두리가 Input의 두 size와 다르다.',
      ],
      dataNotes: [
        '축 3종(담당자·상태·생성일)은 시안이 고정한 목록이라 컴포넌트가 들고 있다. 옵션 데이터(담당자)는 props다.',
        '상태 옵션은 검토 대기·검토 완료 2종이고 하나만 고를 수 있다 — 시안 메모 "하나 만 선택 가능하게(기본이 전체)". 전체로 되돌리는 경로는 "필터 초기화"뿐이라 옵션에 전체를 넣지 않았다.',
        '생성일은 공용 DateRangePicker를 그대로 쓴다 — 시안(18183:138806 Date picker 580×360)의 2개월·구분선·"오늘 선택/초기화"·"닫기/적용" 구성이 그 컴포넌트와 일치해 새로 만들지 않았다. 칩은 커스텀 트리거로 넘긴다.',
        '정렬 옵션은 최근 변경 순·오래된순 2종이다(사용자 확정 8/14, 시안 18183:139128의 2옵션과 개수 일치). 정렬 기준은 lastActivityAt(ISO)이고 표시 문자열("3시간 전")로는 순서를 만들 수 없어 모델에 필드를 추가했다.',
      ],
      tokenNotes: [
        '바 컨테이너: 배경 Fill/Normal/Assistive(흰색) + Line/Normal/Neutral 테두리 + radius 12 + padding 20 + gap 12.',
        '검색창: Fill/Normal/Strong 배경 + Line/Normal/Assistive 1px 테두리 + radius 8 + px 12 py 8, min-h 40.',
        '칩: h 36 + radius 8 + px 10 + gap 8, 아이콘 20. 활성 칩은 "축: 값" 두 조각이고 축 라벨은 shrink-0, 값이 폭을 흡수한다.',
        '드롭다운 카드: radius 12(래퍼 기본 16 오버라이드) + Shadow/Dropdown menu. 폭은 상태 250(w-62.5)·담당자 300(w-75)으로 축마다 다르다.',
      ],
      layoutNotes: [
        '폭을 갖지 않는다 — 1040은 대시보드 콘텐츠 열의 값이고 슬롯이 준다.',
        '폭 흡수는 칩 묶음 하나다(min-w-0 flex-1). 초기화 버튼은 shrink-0이라 좁아져도 밀리지 않는다.',
        '칩 상한 180(max-w-45)·하한 36(min-w-9)은 시안 고정값이고, 긴 값은 그 안에서 잘린다.',
      ],
      interactionNotes: [
        '드롭다운은 포털로 렌더되므로 play는 `canvasElement.ownerDocument.body` 스코프로 찾는다.',
        '담당자 패널은 검색 입력을 갖는다 — Radix 메뉴의 타이핑 탐색이 가로채지 않도록 콘텐츠 안에서 키를 끊는다(검토 큐와 동일).',
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

    // 필터가 없으면 축 칩은 전부 미선택이고 정렬 칩만 선택 톤이다.
    await expect(assigneeChip).toHaveAttribute('data-selected', 'false');
    await expect(sortChip).toHaveAttribute('data-selected', 'true');

    await userEvent.click(canvas.getByRole('button', { name: /필터 초기화/ }));
    await expect(args.onClearFilters).toHaveBeenCalled();
  },
};

/** 활성 필터. 해당 축 칩만 선택 톤이 되고 "축: 값"으로 적힌다. */
export const ActiveStatus: Story = {
  args: { activeAxis: 'status', activeValueLabel: '검토 대기' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const statusChip = canvas.getByRole('button', { name: /^상태/ });
    await expect(statusChip).toHaveAttribute('data-selected', 'true');
    // 두 조각은 flex gap으로 벌어져 있어 문자열에는 공백이 없다.
    await expect(statusChip).toHaveTextContent(/상태:\s*검토 대기/);

    // 다른 축은 켜지지 않는다 — 활성 축은 하나다.
    await expect(canvas.getByRole('button', { name: /담당자/ })).toHaveAttribute('data-selected', 'false');
  },
};

/** 상태 드롭다운. 옵션은 배지 그 자체이고 2종뿐이다. */
export const StatusDropdown: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: /상태/ }));

    const items = await body.findAllByRole('menuitem');
    await expect(items).toHaveLength(2);
    await expect(body.getByText('검토 대기')).toBeInTheDocument();
    await expect(body.getByText('검토 완료')).toBeInTheDocument();

    // 카드 폭은 250 고정이다.
    await expect(window.getComputedStyle(body.getByRole('menu')).width).toBe('250px');

    await userEvent.click(body.getByText('검토 완료'));
    await expect(args.onStatusSelect).toHaveBeenCalledWith('reviewed');
  },
};

/** 담당자 드롭다운. 검토 큐와 같은 검색 멀티셀렉트 패널이 열린다. */
export const AssigneeDropdown: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: /담당자/ }));

    const input = await body.findByPlaceholderText('담당자 검색');
    // Radix 메뉴가 타이핑을 가로채면 입력값이 남지 않는다.
    await userEvent.type(input, '박서');
    await expect(input).toHaveValue('박서');
    await expect(body.getAllByRole('option')).toHaveLength(1);

    // 카드 폭은 300 고정이다(상태 250과 다른 값).
    await expect(window.getComputedStyle(input.closest('[role=menu]') as HTMLElement).width).toBe('300px');

    await userEvent.click(body.getByText('직원10'));
    await expect(args.onAssigneeToggle).toHaveBeenCalledWith('u-seoyeon');
  },
};

/** 정렬 드롭다운. 최근 변경 순·오래된순 2종이고 현재값이 지속 하이라이트된다. */
export const SortDropdown: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: /최근 변경 순/ }));

    const items = await body.findAllByRole('menuitem');
    await expect(items).toHaveLength(2);

    // 적용 중인 정렬만 채움이 있다.
    const recentItem = body.getByText('최근 변경 순', { selector: '[role=menuitem] span' }).closest('[role=menuitem]')!;
    const oldestItem = body.getByText('오래된순').closest('[role=menuitem]')!;
    await expect(getComputedStyle(recentItem).backgroundColor).not.toBe(getComputedStyle(oldestItem).backgroundColor);

    await userEvent.click(body.getByText('오래된순'));
    await expect(args.onSortSelect).toHaveBeenCalledWith('oldest');
  },
};

/** 생성일 칩 → 공용 DateRangePicker. 캘린더 2개월과 액션 바가 열린다. */
export const CreatedAtCalendar: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '생성일' }));

    // 시안대로 2개월이 나란히 뜨고 액션 바가 붙는다.
    await expect(await body.findByRole('button', { name: '오늘 선택' })).toBeInTheDocument();
    await expect(body.getByRole('button', { name: '초기화' })).toBeInTheDocument();
    await expect(body.getByRole('button', { name: '적용' })).toBeInTheDocument();
    await expect(body.getAllByRole('grid')).toHaveLength(2);
  },
};

/** 좁은 슬롯. 칩 묶음이 줄고 초기화 버튼은 밀리지 않아야 한다. */
export const NarrowSlot: Story = {
  args: { activeAxis: 'assignee', activeValueLabel: '직원10, 이진수, 팀원F, 김하은, 최민우' },
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

    await expect(slot.scrollWidth).toBeLessThanOrEqual(slot.clientWidth);

    // 긴 값이 들어와도 칩은 상한 180 안에서 잘린다.
    const assigneeChip = canvas.getByRole('button', { name: /^담당자/ });
    await expect(assigneeChip.getBoundingClientRect().width).toBeLessThanOrEqual(180);

    await expect(canvas.getByRole('button', { name: /필터 초기화/ })).toBeVisible();
  },
};
