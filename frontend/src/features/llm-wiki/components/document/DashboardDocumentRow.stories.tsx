import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { createDocumentRow } from '../../fixtures/llmWikiFixtures';
import DashboardDocumentRow from './DashboardDocumentRow';

const meta = {
  title: 'Compositions/LLM Wiki/Document/DashboardDocumentRow',
  component: DashboardDocumentRow,
  tags: ['autodocs'],
  args: { onClick: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17762-102993',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17762:102993',
      },
      viewport: { width: 1040, height: 140 },
      states: ['default', 'with-error-icon(rule-tbd)'],
      reuseNotes: [
        '대시보드 문서 표(17606:149822) 전용 행이다. 문서_폴더 메인(17762:104801)·문서_채널 메인(17762:103743) 행은 3열이 "연결 VOC & 고객사 수"이고 breadcrumbs가 없어 같은 컴포넌트가 아니다 — 스펙 미결로 분리됐다.',
        '상태 배지는 DocumentStatusBadge(17762:103484)를 그대로 쓴다.',
        'error_filled·file_filled·arrow_right2는 리포에 이미 있는 에셋을 재사용했다. wiki_channel만 신규 export.',
      ],
      dataNotes: [
        '로딩·빈 상태 스토리는 만들지 않는다 — 디자인 MISSING(감사 §7 금지 목록).',
        '에러 아이콘과 "검토 완료" 배지의 공존 규칙은 UNKNOWN — 스토리 이름에 TBD 명시. Figma 대시보드 6개 행은 전부 배지를 달고 있고 그중 상단 3개만 에러 아이콘을 동반한다(17762:102993·17849:106474·17849:106512). 공존이 규칙인지 목업 나열인지 미확정.',
        '태그는 첫 1개만 칩으로 보이고 나머지는 "+N"으로 접힌다 — Figma 태그 칸이 칩 1개(142) + gap 8 + "+2"(34) = 184로 정확히 채워져 있어 칩 슬롯이 1개로 고정이다.',
        '신뢰도·유형 배지는 만들지 않는다 — Figma 행에 없다.',
      ],
      tokenNotes: [
        '제목 #33363D = text-text-normal-normal, heading(sb)/small = text-heading-small.',
        'breadcrumb 라벨 #464C53 = text-text-normal-neutral, 아이콘 #6D7882 = text-icon-normal-neutral, body(md)/xsmall = text-body-xsmall.',
        '문서 아이콘틀 #F7F7F8/#B1B8BE = bg-fill-normal-strong/text-icon-normal-alternative, 충돌 행 #FFFAFA/#FF6363 = bg-accent-red-lighten/text-accent-red-default.',
        '태그 칩 #E5F6FE/#00AEFF = bg-accent-light-blue-lighten/text-accent-light-blue-default, "+N" 칩만 배경이 #F7F7F8 = bg-fill-normal-strong.',
        '최근 활동 #6D7882 = text-text-normal-alternative, 우측 정렬(Figma textAlign RIGHT).',
      ],
      layoutNotes: [
        '4열 grid: minmax(0,1fr) | 194px | 184px | 96px + gap 16. Figma는 좌/우 두 덩어리가 각각 fill이라 1028 - 16 = 1012를 506씩 나눠 갖는데, 우측 506 = 194 + 16 + 184 + 16 + 96이라 4열 grid로 펴면 같은 값이 나온다(1028 - 48 - 474 = 506).',
        '고정폭 3개(194/184/96)는 행끼리·헤더와 열을 맞추기 위한 것이다. 표 헤더가 생기면 DASHBOARD_DOCUMENT_ROW_GRID를 함께 import해 같은 템플릿을 쓴다.',
        '폭 흡수는 문서 열 하나뿐(minmax(0,1fr) + min-w-0). 축소 순서는 제목 truncate → breadcrumb 라벨 truncate → 태그 칩 truncate 순이고, 가로 스크롤은 넣지 않았다.',
        '행 높이 65는 결과값이다(p-1.5 6 + 아이콘틀 40 + 6 … 실제로는 제목 23 + gap 2 + breadcrumb 28 = 53). h-*로 못박지 않는다.',
        'Figma 행 프레임은 fills=[] + borderRadius 8이라 hover 채움이 있을 법하지만 노드에 정의가 없다 — hover 시각을 발명하지 않았다(디자이너 확인 필요).',
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
    await expect(canvas.getByText('3시간 전')).toBeInTheDocument();

    // 태그 3개 중 첫 칩만 보이고 나머지는 +2로 접힌다.
    await expect(canvas.getByText('재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('+2')).toBeInTheDocument();
    await expect(canvas.queryByText('결제 실패')).toBeNull();

    // 선두 아이콘은 viewBox로 구분한다 — 색 비교와 달리 테마에 흔들리지 않는다.
    const row = canvas.getByRole('button');
    await expect(findIconSvg(row)).toHaveAttribute('viewBox', '0 0 18 18');

    // 고정폭 열이 살아 있는지 — 무너지면 행끼리 열이 어긋난다.
    await expect(canvas.getByText('3시간 전').getBoundingClientRect().width).toBe(96);

    await userEvent.click(row);
    await expect(args.onClick).toHaveBeenCalledWith('doc-payment-retry');
  },
};

/** 에러(충돌) 아이콘 행. 상태 배지와의 공존 규칙이 미확정이라 이름에 TBD를 남긴다. */
export const WithErrorIconRuleTBD: Story = {
  args: { document: createDocumentRow({ hasConflictIcon: true }) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button');

    // 선두 아이콘이 충돌 아이콘으로 바뀐다.
    await expect(findIconSvg(row)).toHaveAttribute('viewBox', '0 0 24 24');
    // 충돌 행도 상태 배지를 함께 단다.
    await expect(canvas.getByText('검토 완료')).toBeInTheDocument();
  },
};

/** 좁은 슬롯. 폭이 줄면 고정폭 열이 아니라 문서 열이 흡수하고 제목이 잘려야 한다. */
export const LongTitleInNarrowSlot: Story = {
  args: {
    document: createDocumentRow({
      title: '결제 승인 실패 시 재시도 정책 및 PG사별 예외 처리와 고객 안내 문구 표준화 가이드 문서명 text text text',
    }),
  },
  decorators: [
    (Story) => (
      <div className="w-160 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const row = canvas.getByRole('button');
    const slot = canvasElement.querySelector('div.w-160') as HTMLElement;
    const heading = canvas.getByText(args.document.title);

    // 제목이 늘어나도 행은 슬롯을 넘지 않는다.
    await expect(row.getBoundingClientRect().width).toBeLessThanOrEqual(slot.getBoundingClientRect().width);
    await expect(row.scrollWidth).toBeLessThanOrEqual(row.clientWidth);

    // 고정폭 열은 좁아져도 그대로다 — 줄어드는 쪽은 문서 열이어야 한다.
    await expect(canvas.getByText('3시간 전').getBoundingClientRect().width).toBe(96);

    // truncate가 빠지면 줄바꿈으로 폭은 지키면서 행 높이가 자란다 — 넘침 없음만으로는 부족하다.
    await expect(heading.scrollWidth).toBeGreaterThan(heading.clientWidth);
    await expect(heading.getClientRects()).toHaveLength(1);
  },
};
