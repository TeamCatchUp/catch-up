import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  DOCUMENT_ROW_FIXTURES,
  REVIEW_QUEUE_ASSIGNEE_OPTIONS,
  REVIEW_STAT_CARD_FIXTURES,
} from '../../fixtures/llmWikiFixtures';
import WikiDashboardPage from './WikiDashboardPage';

const meta = {
  title: 'Screens/LLM Wiki/DashboardPage',
  component: WikiDashboardPage,
  tags: ['autodocs'],
  args: {
    stats: REVIEW_STAT_CARD_FIXTURES,
    documents: DOCUMENT_ROW_FIXTURES,
    currentUserName: '팀원F',
    assigneeOptions: REVIEW_QUEUE_ASSIGNEE_OPTIONS,
    pageSize: 20,
    onDocumentClick: fn(),
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
      states: ['default', 'stat-card-filters-table', 'narrow-viewport'],
      reuseNotes: [
        'WikiPageHeader(main)·ReviewStatCard·DashboardDocumentTableHeader·DashboardDocumentRow·WikiSpaceTableFooter를 조립만 한다 — 전부 무수정 소비. 푸터는 채널·폴더 세션 파일이라 소비만 하고 손대지 않았다.',
        '필터 칩은 shared Chip(variant=square)이다 — 미선택 토큰(흰 배경·Line/Normal/Neutral·Text/Normal/Normal)과 선택 토큰(Fill/Primary/Normal/Assistive·Line/Primary/Normal·Text/Primary/Normal)이 시안과 그대로 일치해 새 칩을 만들지 않았다. 시안 gap 8·padding 10만 className으로 덮는다.',
        'align·progress·calendar·person·search_300·cancel_small·dropdown_down·dashboard·kebab_horizontal 전부 기존 에셋이고 Figma 컴포넌트명과 1:1 — 신규 export 없음.',
        '검색창만 직접 조립했다 — 공용 Input에 아이콘 슬롯이 없고, 시안 배경(Fill/Normal/Strong)·테두리(Line/Normal/Assistive)가 Input의 두 size 어느 쪽과도 다르다.',
      ],
      dataNotes: [
        '지표·문서 목록은 전부 fixture다(REVIEW_STAT_CARD_FIXTURES·DOCUMENT_ROW_FIXTURES). 페이지는 API를 부르지 않는다 — Mock 앱 푸시 원칙대로 실 API 도착 시 픽스처 자리만 교체한다.',
        '로딩·빈 목록·에러 스토리는 만들지 않는다 — 디자인 MISSING(감사 §7 금지 목록). 로딩·에러가 없는 것이 이 단계의 정상이다.',
        '지표 카드를 누르면 아래 표에 같은 이름의 필터가 걸린다(사용자 확정 8/14). 매핑과 술어는 순수 모듈 dashboardFilters가 갖고 unit이 지킨다 — 카드·드롭다운이 같은 필터 자리를 놓고 서로를 덮어쓴다.',
        '필터 축은 한 번에 하나만 걸린다. 축을 겹쳐 거는 계약은 시안에 없어 만들지 않았고, 해제 경로는 시안에 있는 "필터 초기화"뿐이다.',
        '검색은 제목 대조다 — 본문·태그 검색은 계약이 없다. 시안이 검색창을 그려 둔 이상 죽은 입력으로 두지 않는 선에서 최소로 붙였다.',
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

    await userEvent.click(canvas.getByText('결제 승인 실패 시 재시도 정책'));
    await expect(args.onDocumentClick).toHaveBeenCalledWith('doc-payment-retry');
  },
};

/** 지표 카드 클릭 → 아래 표가 좁혀지고 해당 축 칩이 "축: 값"으로 켜진다. */
export const StatCardFiltersTable: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const rowCount = () => canvas.getAllByRole('button').filter((el) => el.querySelector('.text-heading-small')).length;

    const before = rowCount();
    const statsGrid = canvasElement.querySelector('div.grid') as HTMLElement;

    // "검토 대기" 카드를 누르면 상태 축이 켜진다.
    await userEvent.click(within(statsGrid).getByText('검토 대기'));

    // 활성화되면 칩 이름이 "상태: 검토 대기"로 바뀐다 — 접두사로 집는다.
    const statusChip = canvas.getByRole('button', { name: /^상태/ });
    // 두 조각은 flex gap으로 벌어져 있어 문자열에는 공백이 없다.
    await expect(statusChip).toHaveTextContent(/상태:\s*검토 대기/);
    await expect(statusChip).toHaveAttribute('data-selected', 'true');

    // 표가 실제로 좁혀졌고, 남은 행은 전부 검토 대기다.
    const after = rowCount();
    await expect(after).toBeLessThan(before);
    await expect(canvas.getAllByText('검토 대기').length).toBeGreaterThan(1);
    await expect(canvas.queryByText('검토 완료')).toBeNull();

    // 초기화하면 원래 목록으로 돌아온다.
    await userEvent.click(canvas.getByRole('button', { name: /필터 초기화/ }));
    await expect(canvas.getByRole('button', { name: '상태' })).toHaveAttribute('data-selected', 'false');
    await expect(rowCount()).toBe(before);
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
