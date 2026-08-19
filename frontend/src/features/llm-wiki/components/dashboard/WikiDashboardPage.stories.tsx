import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  DASHBOARD_ASSIGNEE_OPTIONS,
  DOCUMENT_ROW_FIXTURES,
  REVIEW_STAT_CARD_FIXTURES,
} from '../../fixtures/llmWikiFixtures';
import { INITIAL_DASHBOARD_QUERY_STATE } from './dashboardFilters';
import WikiDashboardPage from './WikiDashboardPage';

const meta = {
  title: 'Screens/LLM Wiki/DashboardPage',
  component: WikiDashboardPage,
  tags: ['autodocs'],
  /** 조회 상태는 소비처(라우트)가 든다 — 스토리는 그 자리를 로컬 state로 대신한다. */
  render: function DashboardStory(args) {
    const [queryState, setQueryState] = useState(args.queryState);

    return (
      <WikiDashboardPage
        {...args}
        queryState={queryState}
        onQueryStateChange={(next) => {
          args.onQueryStateChange(next);
          setQueryState(next);
        }}
      />
    );
  },
  args: {
    stats: REVIEW_STAT_CARD_FIXTURES,
    documents: DOCUMENT_ROW_FIXTURES,
    totalCount: DOCUMENT_ROW_FIXTURES.length,
    assigneeOptions: DASHBOARD_ASSIGNEE_OPTIONS,
    myUserId: 1,
    pageSize: 20,
    queryState: INITIAL_DASHBOARD_QUERY_STATE,
    onQueryStateChange: fn(),
    onDocumentClick: fn(),
    onPageSizeChange: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17595-148922',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17595:148922',
      },
      viewport: { width: 1200, height: 1571 },
      states: [
        'default',
        'stat-card-filters-table',
        'empty-table',
        'empty-by-filter',
        'paged',
        'page-size-dropdown',
        'narrow-viewport',
      ],
      reuseNotes: [
        'WikiPageHeader(main)·ReviewStatCard·DashboardDocumentTableHeader·DashboardDocumentRow·WikiSpaceTableFooter를 조립만 한다. 푸터는 채널·폴더와 공유하는 부품이라 쪽 크기 선택을 optional prop으로만 열고 대시보드만 배선했다(채널·폴더는 종전과 같은 정적 표시).',
        '필터 칩은 shared Chip(variant=square)이다 — 미선택 토큰(흰 배경·Line/Normal/Neutral·Text/Normal/Normal)과 선택 토큰(Fill/Primary/Normal/Assistive·Line/Primary/Normal·Text/Primary/Normal)이 시안과 그대로 일치해 새 칩을 만들지 않았다. 시안 gap 8·padding 10만 className으로 덮는다.',
        'align·progress·calendar·person·search_300·cancel_small·dropdown_down·dashboard·kebab_horizontal 전부 기존 에셋이고 Figma 컴포넌트명과 1:1 — 신규 export 없음.',
        '검색창만 직접 조립했다 — 공용 Input에 아이콘 슬롯이 없고, 시안 배경(Fill/Normal/Strong)·테두리(Line/Normal/Assistive)가 Input의 두 size 어느 쪽과도 다르다.',
      ],
      dataNotes: [
        '화면은 데이터를 props로만 받는다 — 목록·지표 요청은 라우트의 페이지 모델 훅(useWikiDashboardModel)이 GET /wiki/artifacts로 낸다. 스토리는 MSW 없이 fixture를 그대로 주입한다.',
        '필터·검색·정렬·쪽 이동은 전부 서버 파라미터로 나간다(q·status·owner_user_id|unassigned·created_after·created_before·sort·order·limit·offset). 그래서 스토리에서 필터를 걸어도 fixture 표는 좁혀지지 않는다 — 검증 대상은 방출되는 조회 상태다.',
        '담당자 2인 이상 선택만 서버 파라미터로 표현되지 않아 받은 쪽에서 한 번 더 좁힌다(owner_user_id는 한 명뿐). 그 좁히기는 훅이 맡고 화면은 관여하지 않는다.',
        '지표 4종은 집계 API가 없어 limit=1 목록의 total로 센다. "내 담당"은 내 user_id가 있어야 성립해서, 없으면 카드가 누를 수 없는 상태로 렌더된다.',
        '빈 목록은 8/14 시안(18234:49957) 도착으로 구현했다 — 헤더는 남고 행 자리에 안내가 들어간다. 필터 결과 0건도 같은 안내를 쓴다(시안이 하나뿐이라 문구를 가르지 않는다). 로딩·에러는 여전히 MISSING이라 만들지 않는다 — 로딩은 이전 쪽 유지, 에러는 빈 표다.',
        '지표 카드를 누르면 아래 표에 같은 이름의 필터가 걸린다(사용자 확정 8/14). 매핑과 파라미터 변환은 순수 모듈 dashboardFilters가 갖고 unit이 지킨다 — 카드·드롭다운이 같은 필터 자리를 놓고 서로를 덮어쓴다.',
        '필터 축은 한 번에 하나만 걸린다. 축을 겹쳐 거는 계약은 시안에 없어 만들지 않았고, 해제 경로는 시안에 있는 "필터 초기화"뿐이다.',
        '검색은 제목 부분 일치(q)다 — 본문·태그 검색은 계약이 없다.',
        '표 푸터 우측의 같은 페이지 크기 컨트롤은 렌더하지 않는다 — 레이어명이 "Page Size (중복?)"이라 디자이너 본인이 중복을 의심하고 있다.',
      ],
      tokenNotes: [
        '페이지 제목 heading(sb)/xlarge #33363D, 부제 body(md)/small #6D7882 = text-text-normal-alternative, 사이 gap 4.',
        '필터 바: 배경 Fill/Normal/Assistive(흰색) + Line/Normal/Neutral 테두리 + radius 12 + padding 20 + gap 12.',
        '검색창: Fill/Normal/Strong 배경 + Line/Normal/Assistive 1px 테두리 + radius 8 + px 12 py 8, min-h 40. placeholder Text/Normal/Assistive.',
        '필터 초기화: heading(sb)/small + Text/Normal/Alternative, 아이콘 cancel_small 20 + gap 6, h 36.',
      ],
      layoutNotes: [
        '본문 px-20(80)은 헤더 px-16(64)과 다른 값이다 — 시안이 갈라 뒀고 헤더 컴포넌트가 자기 패딩을 가진다.',
        '세로 리듬 실측: 제목 블록 pt-9(36) → 섹션 gap-10(40) → 섹션 사이 gap-6(24) → 표↔푸터 gap-8(32) → 행 사이 gap-1(4). 페이지 하단 pb-9(36).',
        '스탯은 grid-cols-4 gap-5다 — 1040 = 245×4 + 20×3. 8/14 시안에서 지표가 4종으로 확정되며 빈 슬롯 문제가 사라졌다(#26 해소).',
        '폭 흡수는 층마다 하나다 — 필터 행에서는 칩 묶음(min-w-0 flex-1), 표 행에서는 문서 열. 초기화 버튼·푸터 컨트롤은 shrink-0.',
      ],
    }),
  },
} satisfies Meta<typeof WikiDashboardPage>;

export default meta;
type Story = StoryObj<typeof WikiDashboardPage>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 헤더 제목과 본문 제목이 둘 다 "대시보드"다 — 시안 그대로이고 중복이 아니다.
    await expect(canvas.getAllByText('대시보드')).toHaveLength(2);
    await expect(canvas.getByText('오늘 확인해야 할 지식과 최근 업데이트를 한곳에서 관리하세요.')).toBeInTheDocument();

    // 지표는 스탯 영역으로 좁혀 센다 — "검토 대기"는 표의 상태 배지에도 있어 전역 조회로는 잡히지 않는다.
    const statsGrid = canvasElement.querySelector('div.grid') as HTMLElement;
    const stats = within(statsGrid);
    for (const stat of REVIEW_STAT_CARD_FIXTURES) {
      await expect(stats.getByText(stat.label)).toBeInTheDocument();
    }
    // 4슬롯 그리드가 지표 4종으로 정확히 채워진다.
    await expect(statsGrid.children).toHaveLength(4);

    await expect(canvas.getByText('결제 승인 실패 시 재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('계정 삭제 요청과 보관 기간')).toBeInTheDocument();

    // 필터 바 4칩 + 초기화. 지표 카드도 버튼이라 축 칩은 이름 완전일치로 집는다
    // ("담당자 미지정" 카드가 /담당자/에 함께 걸린다).
    await expect(canvas.getByRole('button', { name: '담당자' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '상태' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '생성일' })).toBeInTheDocument();
    await expect(canvas.getByPlaceholderText('검색어를 입력하세요.')).toBeInTheDocument();

    // 정렬 칩만 선택 톤이다 — 나머지 칩과 배경이 갈려야 한다.
    const sortChip = canvas.getByRole('button', { name: /최근 변경 순/ });
    const assigneeChip = canvas.getByRole('button', { name: '담당자' });
    await expect(sortChip).toHaveAttribute('data-selected', 'true');
    await expect(getComputedStyle(sortChip).backgroundColor).not.toBe(getComputedStyle(assigneeChip).backgroundColor);

    // 행 클릭은 오버레이 버튼(접근명=제목)으로 흐른다 — 제목 텍스트는 오버레이 아래라 직접 못 누른다.
    await userEvent.click(canvas.getByRole('button', { name: '결제 승인 실패 시 재시도 정책' }));
    await expect(args.onDocumentClick).toHaveBeenCalledWith('doc-payment-retry');
  },
};

/** 지표 카드 클릭 → 해당 축 칩이 "축: 값"으로 켜지고 조회 상태에 서버 필터가 실린다. */
export const StatCardFiltersTable: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const statsGrid = canvasElement.querySelector('div.grid') as HTMLElement;

    // "검토 대기" 카드를 누르면 상태 축이 켜진다.
    await userEvent.click(within(statsGrid).getByText('검토 대기'));

    // 활성화되면 칩 이름이 "상태: 검토 대기"로 바뀐다 — 접두사로 집는다.
    const statusChip = canvas.getByRole('button', { name: /^상태/ });
    // 두 조각은 flex gap으로 벌어져 있어 문자열에는 공백이 없다.
    await expect(statusChip).toHaveTextContent(/상태:\s*검토 대기/);
    await expect(statusChip).toHaveAttribute('data-selected', 'true');

    // 좁히기는 서버 몫이다 — 카드 클릭은 조회 상태로 나가고 쪽은 1로 돌아간다.
    await expect(args.onQueryStateChange).toHaveBeenCalledWith(
      expect.objectContaining({
        filter: expect.objectContaining({ kind: 'status', status: 'pending_review' }),
        page: 1,
      }),
    );

    // "내 담당"은 내 user_id를 필터로 싣는다.
    await userEvent.click(within(statsGrid).getByText('내 담당'));
    await expect(args.onQueryStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        filter: expect.objectContaining({ kind: 'assignee', ownerUserIds: [1] }),
      }),
    );

    // 초기화하면 축이 전부 꺼진다.
    await userEvent.click(canvas.getByRole('button', { name: /필터 초기화/ }));
    await expect(canvas.getByRole('button', { name: '상태' })).toHaveAttribute('data-selected', 'false');
    await expect(canvas.getByRole('button', { name: '담당자' })).toHaveAttribute('data-selected', 'false');
  },
};

/** 내 user_id가 없을 때. "내 담당" 카드는 누를 수 없고 나머지 지표는 그대로 동작한다. */
export const WithoutCurrentUser: Story = {
  args: { myUserId: undefined },
  play: async ({ canvasElement }) => {
    const statsGrid = canvasElement.querySelector('div.grid') as HTMLElement;
    const stats = within(statsGrid);

    await expect(stats.queryByRole('button', { name: /내 담당/ })).toBeNull();
    await expect(stats.getByRole('button', { name: /검토 대기/ })).toBeInTheDocument();
  },
};

/** 문서가 없을 때. 헤더는 남고 행 자리에 안내가 들어간다(8/14 시안 도착분). */
export const EmptyTable: Story = {
  args: { documents: [], totalCount: 0 },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('문서가 없어요')).toBeInTheDocument();
    // 헤더는 그대로 남는다 — 빈 상태가 표를 통째로 지우지 않는다.
    await expect(canvas.getByText('최근 활동')).toBeInTheDocument();
  },
};

/** 검색 결과가 0건일 때도 같은 안내를 쓴다. 검색어는 조회 상태로 나가 q가 된다. */
export const EmptyByFilter: Story = {
  args: {
    documents: [],
    totalCount: 0,
    queryState: { ...INITIAL_DASHBOARD_QUERY_STATE, keyword: '존재하지않는문서제목' },
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const search = canvas.getByPlaceholderText('검색어를 입력하세요.');

    await expect(search).toHaveValue('존재하지않는문서제목');
    await expect(canvas.getByText('문서가 없어요')).toBeInTheDocument();

    // 타건은 조회 상태로 나가고 쪽은 1로 돌아간다 — 목록 요청은 소비처가 만든다.
    await userEvent.type(search, '!');
    await expect(args.onQueryStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ keyword: '존재하지않는문서제목!', page: 1 }),
    );
  },
};

/** 쪽 수는 서버가 준 total에서 나온다 — 쪽을 옮기면 조회 상태의 page가 바뀐다. */
export const Paged: Story = {
  args: { totalCount: 47 },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 47건 ÷ 20 = 3쪽.
    await expect(canvas.getByRole('button', { name: '3' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '4' })).toBeNull();

    await userEvent.click(canvas.getByRole('button', { name: '2' }));
    await expect(args.onQueryStateChange).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }));
  },
};

/**
 * 쪽 크기 드롭다운. 푸터의 표시가 그대로 트리거고 옵션은 10·20·30·40·50 5종이다.
 * 고른 값은 소비처로 나가고 그것을 다시 받아 표시한다 — limit 파라미터는 소비처가 만든다.
 */
export const PageSizeDropdown: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const body = within(canvasElement.ownerDocument.body);

    await userEvent.click(canvas.getByRole('button', { name: '20' }));

    const items = await body.findAllByRole('menuitem');
    await expect(items.map((item) => item.textContent)).toEqual(['10', '20', '30', '40', '50']);

    // 카드 폭은 트리거 폭 변수에 묶여 있다 — 풀리면 드롭다운 기본 최소폭(200)이 숫자 하나에 남는다.
    const menuStyle = getComputedStyle(body.getByRole('menu'));
    await expect(parseFloat(menuStyle.width)).toBeCloseTo(
      parseFloat(menuStyle.getPropertyValue('--radix-dropdown-menu-trigger-width')),
      1,
    );

    // 적용 중인 크기만 채움이 있다.
    await expect(getComputedStyle(items[1]).backgroundColor).not.toBe(getComputedStyle(items[0]).backgroundColor);

    await userEvent.click(items[3]);
    await expect(args.onPageSizeChange).toHaveBeenCalledWith(40);
  },
};

/**
 * 좁은 뷰포트. 표의 고정폭 열은 그대로고 문서 열만 줄어야 하며,
 * 필터 바는 가로 스크롤 없이 버텨야 한다.
 */
export const NarrowViewport: Story = {
  decorators: [
    (Story) => (
      <div className="w-240 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const slot = canvasElement.querySelector('div.w-240') as HTMLElement;

    // 페이지가 슬롯을 넘지 않는다 — 넘치면 화면 전체에 가로 스크롤이 생긴다.
    await expect(slot.scrollWidth).toBeLessThanOrEqual(slot.clientWidth);

    // 최근 활동 열은 좁아져도 96 고정이다.
    await expect(canvas.getAllByText('3시간 전')[0].getBoundingClientRect().width).toBe(96);

    // 제목은 잘리되 한 줄을 유지한다.
    const title = canvas.getByText('신규 고객사 온보딩 체크리스트');
    await expect(title.getClientRects()).toHaveLength(1);
  },
};
