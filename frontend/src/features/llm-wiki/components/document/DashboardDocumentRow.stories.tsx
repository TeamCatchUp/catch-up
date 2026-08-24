import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { createDocumentRow, DOCUMENT_ROW_FIXTURES } from '../../fixtures/llmWikiFixtures';
import DashboardDocumentRow, { DashboardDocumentTableHeader } from './DashboardDocumentRow';

const meta = {
  title: 'Compositions/LLM Wiki/Document/DashboardDocumentRow',
  component: DashboardDocumentRow,
  tags: ['autodocs'],
  args: { onClick: fn(), onBreadcrumbClick: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17606-149816',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17606:149816',
      },
      viewport: { width: 1040, height: 240 },
      states: [
        'default(reviewed)',
        'pending-review',
        'multiple-owners',
        'multiple-owners-grow-row',
        'unassigned-owner',
        'hover',
        'table-alignment',
        'long-title-narrow-slot',
      ],
      reuseNotes: [
        '상태 배지는 DocumentStatusBadge를 그대로 쓴다 — 새 표 행의 배지(18122:60892)가 기존 md 규격(px-2 py-1·gap-2·아이콘 20)과 일치함을 재실측.',
        '담당자 아바타는 공용 Avatar(size small=25) + 시안 인스턴스 오버라이드(radius 12·line-assistive 링) — ReviewQueueRow와 같은 조합(중복 감사 #2의 DS 드리프트 기록 참조).',
        'file_filled·arrow_right2·wiki_channel·folder 에셋 재사용 — 신규 export 없음. 표 헤더는 같은 파일의 DashboardDocumentTableHeader로 제공.',
        'breadcrumb 마디는 공용 Button(text-secondary-mono·sm) — 18539:60773 Text Button 실측(px 6/py 4·gap 4·radius full·높이 28)과 규격 일치. 라벨·아이콘 색은 실측값 유지로 오버라이드.',
      ],
      dataNotes: [
        '2026-08-13 재실측(대시보드 17595:148922): 태그 열이 소멸하고 담당자(아바타+이름) 열로 교체됐다 — tags·hasConflictIcon 계약 제거.',
        '충돌(error) 아이콘 행이 새 표 15행 어디에도 없다 — 구 "배지·에러 공존 규칙" 질문은 "충돌 표시 이동처" 질문으로 대체(design-request).',
        '담당자 미지정 행은 디자이너 확정 노드 18929:96828 규격 적용(2026-08-24) — 기본 프로필 아바타 + "담당자 없음" 문구. 아바타는 1인 표기와 같은 조합이고, 문구는 이 행의 담당자 열 스케일(body/small)에 색만 text-text-normal-assistive(#B1B8BE)다.',
        '담당자는 실 API(GET /wiki/artifacts) owners[] 복수 계약이다. 2인 이상은 세로 스택으로 전원 렌더한다(사용자 확정) — 시안 MISSING이라 아바타 그룹·+N 배지 대신 1인 표기를 그대로 쌓은 자작 표기다.',
        '로딩 골격은 표 단위(DocumentTableSkeleton)라 이 행에는 없다. 빈 상태 스토리도 만들지 않는다 — 디자인 MISSING 유지.',
      ],
      tokenNotes: [
        '제목 #33363D = text-text-normal-normal + heading(sb)/small 유지. 담당자명 #33363D + body(md)/small.',
        '아바타 링 #F4F4F5 = border-line-normal-assistive, radius 12 = rounded-xl(DS 원본 rounded-full과 갈리는 화면 인스턴스 값).',
        '최근 활동 #6D7882 = text-text-normal-alternative + body(md)/small, 우측 정렬(Figma textAlign RIGHT). 헤더 라벨도 같은 색·타이포.',
        '행 hover는 DS 중립 상호작용 토큰 fill-normal-interaction-hover(#1E2124 6% 알파)다 — 시안에 hover 정의가 없어 채택한 값이고 사용자 확정분이다. 알파라 흰 배경 위에서 #F2F2F2로 합성되어 아이콘틀(#F7F7F8)이 묻히지 않고, 다크는 #F4F5F6 4%로 자동 전환된다. 같은 계열 ReviewQueueRow와 동일 조합.',
        'breadcrumb 마디: 라벨 #464C53 = text-text-normal-neutral body(md)/xsmall, 아이콘 #6D7882 = text-icon-normal-neutral — 기존 값 유지.',
      ],
      layoutNotes: [
        '표는 2셀 구조다: 문서 열(fill, min-w 220) + 메타 셀(고정 428). 바깥 gap 36 = gap-9, 메타 안 gap 16 = gap-4 — gap이 달라 한 층 grid로 펼 수 없다.',
        '메타 셀은 grid-cols-[140px_160px_96px]이고 헤더·행이 DASHBOARD_DOCUMENT_META_GRID 상수를 공유한다. 1040 검산: 6+564+36+140+16+160+16+96+6.',
        '행 셸 시각 분리 약속 이행: rounded-lg는 행 버튼만 갖고 DASHBOARD_DOCUMENT_TABLE_SHELL은 레이아웃만 갖는다(헤더가 함께 쓴다).',
        'breadcrumb 마디 max-w 150(시안 Text Button 150×28 실측, 8/17 재확인) — 초과분은 라벨 truncate. 폭 흡수는 문서 열 하나뿐이고 행 높이 65는 결과값.',
        '행 클릭은 absolute inset-0 오버레이 버튼(접근명=제목) — 마디가 실버튼이 되면서 중첩 버튼을 피하는 구조. 마디 버튼은 relative로 오버레이 위에 뜬다.',
      ],
    }),
  },
} satisfies Meta<typeof DashboardDocumentRow>;

export default meta;
type Story = StoryObj<typeof DashboardDocumentRow>;

const findIconSvg = (element: HTMLElement) => element.querySelector('svg');

export const Default: Story = {
  args: { document: createDocumentRow() },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('결제 승인 실패 시 재시도 정책')).toBeInTheDocument();
    // breadcrumbs는 join된 한 덩어리가 아니라 마디별 라벨로 렌더된다.
    await expect(canvas.getByText('결제')).toBeInTheDocument();
    await expect(canvas.getByText('승인·실패 처리')).toBeInTheDocument();
    await expect(canvas.getByText('검토 완료')).toBeInTheDocument();
    await expect(canvas.getByText('팀원F')).toBeInTheDocument();
    await expect(canvas.getByText('3시간 전')).toBeInTheDocument();

    // 선두 아이콘은 viewBox로 구분한다 — 색 비교와 달리 테마에 흔들리지 않는다.
    await expect(findIconSvg(canvasElement)).toHaveAttribute('viewBox', '0 0 18 18');

    // 고정폭 열이 살아 있는지 — 무너지면 행끼리 열이 어긋난다.
    await expect(canvas.getByText('3시간 전').getBoundingClientRect().width).toBe(96);

    // 마디 클릭은 마디 콜백만 부르고 행 이동을 유발하지 않는다.
    await userEvent.click(canvas.getByRole('button', { name: '결제' }));
    await expect(args.onBreadcrumbClick).toHaveBeenCalledWith({ kind: 'channel', label: '결제' });
    await expect(args.onClick).not.toHaveBeenCalled();

    // 행 클릭은 오버레이 버튼(접근명=제목)으로 흐른다.
    await userEvent.click(canvas.getByRole('button', { name: '결제 승인 실패 시 재시도 정책' }));
    await expect(args.onClick).toHaveBeenCalledWith('doc-payment-retry');
  },
};

/** 검토 대기 행. 표에 노출되는 두 번째 배지 상태다(시안 표의 다수 행). */
export const PendingReview: Story = {
  args: { document: DOCUMENT_ROW_FIXTURES[1] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('검토 대기')).toBeInTheDocument();
    await expect(canvas.getByText('직원10')).toBeInTheDocument();
    // 새 시안의 날짜형 표기도 같은 문자열 계약으로 흐른다.
    await expect(canvas.getByText('2024.12.12')).toBeInTheDocument();
  },
};

/** 담당자 2인 이상. 전원을 세로로 쌓고 행 높이가 그만큼 늘어난다(사용자 확정). */
export const MultipleOwners: Story = {
  args: {
    document: createDocumentRow({
      owners: [
        { userId: 1, displayName: '팀원F', profileImageUrl: null },
        { userId: 12, displayName: '남궁현', profileImageUrl: null },
      ],
    }),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const first = canvas.getByText('팀원F');
    const second = canvas.getByText('남궁현');

    // 전원이 렌더되고 아바타도 인원수만큼 선다.
    await expect(canvasElement.querySelectorAll('.border-line-normal-assistive')).toHaveLength(2);

    // 가로가 아니라 세로로 쌓인다 — 좌변이 같고 둘째 줄이 아래에 온다.
    await expect(second.getBoundingClientRect().left).toBeCloseTo(first.getBoundingClientRect().left, 1);
    await expect(second.getBoundingClientRect().top).toBeGreaterThan(first.getBoundingClientRect().bottom);

    // 고정폭 열은 담당자 수와 무관하게 그대로다.
    await expect(canvas.getByText('3시간 전').getBoundingClientRect().width).toBe(96);
  },
};

/** 담당자가 늘면 행이 높아지는 것을 허용한다 — 1인 행보다 커져야 스택이 잘린 게 아니다. */
export const MultipleOwnersGrowRow: Story = {
  args: { document: createDocumentRow() },
  render: () => (
    <div className="flex w-260 flex-col gap-1">
      <DashboardDocumentRow document={createDocumentRow({ id: 'row-single' })} />
      <DashboardDocumentRow
        document={createDocumentRow({
          id: 'row-triple',
          title: '세 명이 맡은 문서',
          owners: [
            { userId: 1, displayName: '팀원F', profileImageUrl: null },
            { userId: 12, displayName: '남궁현', profileImageUrl: null },
            { userId: 13, displayName: '서지호', profileImageUrl: null },
          ],
        })}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const singleRow = canvas.getByRole('button', { name: '결제 승인 실패 시 재시도 정책' }).parentElement!;
    const tripleRow = canvas.getByRole('button', { name: '세 명이 맡은 문서' }).parentElement!;

    await expect(canvas.getByText('서지호')).toBeInTheDocument();
    await expect(tripleRow.getBoundingClientRect().height).toBeGreaterThan(singleRow.getBoundingClientRect().height);
  },
};

/** 담당자 미지정(빈 배열). 기본 아바타 + "담당자 없음" 문구가 선다 — 열 폭은 유지된다. */
export const UnassignedOwner: Story = {
  args: { document: createDocumentRow({ owners: [] }) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByText('팀원F')).toBeNull();
    // 이름 대신 기본 프로필 폴백 아바타 + 문구가 선다 — 빈 칸이 되살아나면 여기서 잡힌다.
    await expect(canvas.getByText('담당자 없음')).toBeInTheDocument();
    await expect(canvasElement.querySelector('svg[viewBox="0 0 40 40"]')).not.toBeNull();
    await expect(canvasElement.querySelector('.border-line-normal-assistive')).not.toBeNull();

    await expect(canvas.getByText('3시간 전').getBoundingClientRect().width).toBe(96);
  },
};

/**
 * 행 hover. 시안에 없는 상태라 DS 토큰 채택분이다.
 * 합성 이벤트는 CSS :hover를 발동시키지 못해 계산된 색으로는 잴 수 없다 — 토큰이 걸려 있는지와
 * 아이콘틀이 같은 색으로 묻히지 않는지를 대신 못박는다(실제 색 변화는 Storybook에서 눈으로 확인).
 */
export const Hover: Story = {
  args: { document: createDocumentRow() },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button', { name: '결제 승인 실패 시 재시도 정책' }).parentElement!;

    // 토큰이 빠지면 hover가 조용히 사라진다.
    await expect(row.className).toContain('hover:bg-fill-normal-interaction-hover');
    await expect(row.className).toContain('transition-colors');

    // 아이콘틀은 자기 배경(Fill/Normal/Strong 솔리드)을 갖는다 — 행 채움과 같은 토큰이면 hover에서 묻힌다.
    const iconBox = row.querySelector('.bg-fill-normal-strong') as HTMLElement;
    await expect(iconBox).not.toBeNull();
    await expect(iconBox.className).not.toContain('fill-normal-interaction-hover');
  },
};

/** 헤더 + 행 조합. 열 정렬은 눈이 아니라 공유 상수가 보장하는지 좌표로 잰다. */
export const TableAlignment: Story = {
  args: { document: DOCUMENT_ROW_FIXTURES[0] },
  render: () => (
    <div className="flex w-260 flex-col gap-1">
      <DashboardDocumentTableHeader />
      {DOCUMENT_ROW_FIXTURES.map((row) => (
        <DashboardDocumentRow key={row.id} document={row} />
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 담당자 열: 헤더 셀 좌변 == 행의 담당자 셀 좌변.
    const ownerHeader = canvas.getByText('담당자');
    const ownerCell = canvas.getByText('팀원F').parentElement!;
    await expect(ownerCell.getBoundingClientRect().left).toBeCloseTo(ownerHeader.getBoundingClientRect().left, 1);

    // 최근 활동 열: 우측 정렬 열이라 우변으로 잰다.
    const activityHeader = canvas.getByText('최근 활동');
    const activityCell = canvas.getByText('3시간 전');
    await expect(activityCell.getBoundingClientRect().right).toBeCloseTo(
      activityHeader.getBoundingClientRect().right,
      1,
    );

    // 행마다 검산이 흔들리지 않는지 두 번째 행(검토 대기)도 같은 열에 있어야 한다.
    const pendingOwnerCell = canvas.getByText('직원10').parentElement!;
    await expect(pendingOwnerCell.getBoundingClientRect().left).toBeCloseTo(
      ownerHeader.getBoundingClientRect().left,
      1,
    );
  },
};

/** 좁은 슬롯. 폭이 줄면 고정폭 열이 아니라 문서 열이 흡수하고 제목이 잘려야 한다. */
export const LongTitleInNarrowSlot: Story = {
  args: {
    document: createDocumentRow({
      title: '결제 승인 실패 시 재시도 정책 및 PG사별 예외 처리와 고객 안내 문구 표준화 가이드 문서명 text text text',
      breadcrumbs: [
        { kind: 'channel', label: '아주 길게 늘어난 채널 이름 표본' },
        { kind: 'folder', label: '아주 길게 늘어난 폴더 이름 표본' },
      ],
    }),
  },
  decorators: [
    (Story) => (
      <div className="w-200 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    // 오버레이 버튼(접근명=제목)의 부모가 행 셸이다.
    const row = canvas.getByRole('button', { name: args.document.title }).parentElement!;
    const slot = canvasElement.querySelector('div.w-200') as HTMLElement;
    const heading = canvas.getByText(args.document.title);

    // 제목이 늘어나도 행은 슬롯을 넘지 않는다.
    await expect(row.getBoundingClientRect().width).toBeLessThanOrEqual(slot.getBoundingClientRect().width);
    await expect(row.scrollWidth).toBeLessThanOrEqual(row.clientWidth);

    // 고정폭 열은 좁아져도 그대로다 — 줄어드는 쪽은 문서 열이어야 한다.
    await expect(canvas.getByText('3시간 전').getBoundingClientRect().width).toBe(96);

    // truncate가 빠지면 줄바꿈으로 폭은 지키면서 행 높이가 자란다 — 넘침 없음만으로는 부족하다.
    await expect(heading.scrollWidth).toBeGreaterThan(heading.clientWidth);
    await expect(heading.getClientRects()).toHaveLength(1);

    // breadcrumb 마디는 150 상한을 지키고 초과분은 라벨이 잘린다.
    const crumbLabel = canvas.getByText('아주 길게 늘어난 채널 이름 표본');
    const crumb = crumbLabel.parentElement!;
    await expect(crumb.getBoundingClientRect().width).toBeLessThanOrEqual(150);
    await expect(crumbLabel.scrollWidth).toBeGreaterThan(crumbLabel.clientWidth);
  },
};
