import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  CHANNEL_FOLDER_ROW_FIXTURES,
  createFolderDocumentRow,
  FOLDER_DOCUMENT_ROW_FIXTURES,
} from '../../fixtures/llmWikiSpaceFixtures';
import FolderDocumentRow, { FolderDocumentTableHeader } from './FolderDocumentRow';

const meta = {
  title: 'Compositions/LLM Wiki/Document/FolderDocumentRow',
  component: FolderDocumentRow,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18160-82761',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18160:82761',
      },
      viewport: { width: 1040, height: 240 },
      states: [
        'folder-row',
        'document-row',
        'multiple-owners',
        'unassigned-owner',
        'table-alignment',
        'long-name-narrow-slot',
        'without-click',
      ],
      interactionNotes: [
        '행 전체가 하나의 버튼이다 — 메타 칸에 별도 조작 대상이 없다.',
        '[8/24 사용자 지시] hover 채움·커서는 시안 두 노드에 정의가 없어 대시보드 행의 관례(fill-normal-interaction-hover + transition-colors, D7 사용자 확정분)를 그대로 따랐다. onClick이 없는 행에는 걸지 않는다.',
      ],
      reuseNotes: [
        '셸(padding 6·gap 36)과 문서 행의 메타 열은 대시보드 표와 동일 실측이라 DASHBOARD_DOCUMENT_TABLE_SHELL·META_GRID 상수를 공유한다.',
        '담당자 아바타·상태 배지·최근 활동 열은 DashboardDocumentRow와 같은 조합(공용 Avatar small 25 + line-assistive 링, DocumentStatusBadge md).',
        'folder_filled·file_filled 에셋 재사용 — 신규 export 없음.',
      ],
      dataNotes: [
        '2026-08-13 재실측(채널 17724:185191·폴더 17762:104787): 8/5의 VOC·고객사 아이콘 쌍 행이 담당자·상태·최근 활동 열로 교체됐다.',
        '행 상태는 시안에 도시된 검토 완료만 픽스처로 쓴다 — 다른 상태 행·폴더 배지 집계 의미는 미도시(디자이너 질문 유지).',
        '[8/24] 폴더 행은 담당자·상태 열을 두지 않는다 — 폴더에 대응 필드가 없어 항상 빈 열이었다. 시안 두 노드는 mock 데이터로 네 열을 모두 채우지만 실 응답에는 없다(사용자 지시).',
        '담당자는 문서 행에만 있는 owners[] 복수 계약이다. 2인 이상은 세로 스택으로 전원 렌더한다(사용자 확정) — 대시보드 행과 같은 표기이고 시안 없이 정한 자작분이다.',
        '담당자 미지정 행은 디자이너 확정 노드 18929:96828 규격 적용(2026-08-24) — 기본 프로필 아바타 + "담당자 없음" 문구, 대시보드 행과 동일 조합(문구는 열 스케일 body/small + text-text-normal-assistive).',
      ],
      tokenNotes: [
        '이름 #33363D = text-text-normal-normal + heading(sb)/small. 아이콘 셸 #F7F7F8 = bg-fill-normal-strong, 아이콘 #B1B8BE = text-icon-normal-alternative.',
        '최근 활동 #6D7882 = text-text-normal-alternative + body(md)/small — [8/24 재실측] 시안 텍스트 스타일이 가운데 정렬(15:90)이라 우측→가운데로 교정했다. 대시보드 표는 이 세션 범위 밖이라 우측 정렬이 남아 있다.',
        '상태 배지 #D9F7EB/#00985A = accent-green-neutral/accent-green-default — 실측과 토큰이 이미 일치해 바꾼 값이 없다.',
      ],
      layoutNotes: [
        '경로 줄이 없는 1줄 행이라 행 높이 52는 결과값(6+40+6)이다 — h-*를 두지 않는다. 담당자가 2인 이상이면 스택 높이가 아이콘 40을 넘겨 행이 그만큼 자란다.',
        '문서 행: 폭 흡수는 이름 열 하나뿐이고 메타 그리드 140/160/96·gap 16은 고정 — 검산 6+564+36+140+16+160+16+96+6=1040.',
        '폴더 행: 메타 그리드가 96 한 칸이라 이름 열이 그만큼(140+16+160+16=332) 더 흡수한다.',
      ],
    }),
  },
} satisfies Meta<typeof FolderDocumentRow>;

export default meta;
type Story = StoryObj<typeof FolderDocumentRow>;

// 선두 아이콘 구분: folder_filled는 루트 fill="currentColor", file_filled는 fill="none" — viewBox가 같아 fill로 가른다.
const leadingIconFill = (row: HTMLElement) => row.querySelector('svg')?.getAttribute('fill');

/** 폴더 행 — 메타 열이 최근 활동 한 칸뿐이다(담당자·상태는 폴더에 대응 필드가 없다). */
export const FolderRow: Story = {
  args: { kind: 'folder', item: CHANNEL_FOLDER_ROW_FIXTURES[0] },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('승인·실패 처리')).toBeInTheDocument();
    await expect(canvas.getByText('2일 전')).toBeInTheDocument();

    const row = canvas.getByRole('button');
    await expect(leadingIconFill(row)).toBe('currentColor');

    // hover 채움·포인터는 클래스로 잰다 — 계산된 배경색은 hover 상태를 반영하지 않는다.
    await expect(row).toHaveClass('cursor-pointer', 'hover:bg-fill-normal-interaction-hover');

    // 메타 칸은 하나뿐이다 — 빈 담당자·상태 칸이 되살아나면 여기서 잡힌다.
    const meta = row.lastElementChild as HTMLElement;
    await expect(meta.children).toHaveLength(1);
    await expect(canvas.queryByText('검토 완료')).toBeNull();

    // 고정폭 열이 살아 있는지 — 무너지면 행끼리 열이 어긋난다.
    await expect(canvas.getByText('2일 전').getBoundingClientRect().width).toBe(96);

    await userEvent.click(row);
    await expect(args.onClick).toHaveBeenCalledWith('folder-approval-failure');
  },
};

/** 문서 행 — 담당자·상태·최근 활동 세 칸이 문서 목록 응답으로 채워진다. */
export const DocumentRow: Story = {
  args: { kind: 'document', item: FOLDER_DOCUMENT_ROW_FIXTURES[0] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('결제 승인 실패 시 재시도 정책')).toBeInTheDocument();
    await expect(canvas.getByText('팀원F')).toBeInTheDocument();
    await expect(canvas.getByText('검토 완료')).toBeInTheDocument();

    const row = canvas.getByRole('button');
    await expect(leadingIconFill(row)).toBe('none');
    await expect(row).toHaveClass('cursor-pointer', 'hover:bg-fill-normal-interaction-hover');
  },
};

/** 갈 곳이 없는 행 — hover 채움도 포인터도 걸지 않는다(죽은 어포던스 방지). */
export const WithoutClick: Story = {
  args: { kind: 'folder', item: CHANNEL_FOLDER_ROW_FIXTURES[0], onClick: undefined },
  play: async ({ canvasElement }) => {
    const row = within(canvasElement).getByRole('button');

    await expect(row).not.toHaveClass('cursor-pointer');
    await expect(row).not.toHaveClass('hover:bg-fill-normal-interaction-hover');
  },
};

/** 담당자 2인 이상. 전원을 세로로 쌓고 행 높이가 그만큼 늘어난다(사용자 확정). */
export const MultipleOwners: Story = {
  args: {
    kind: 'document',
    item: createFolderDocumentRow({
      owners: [
        { userId: 1, displayName: '팀원F', profileImageUrl: null },
        { userId: 5, displayName: '남궁현', profileImageUrl: null },
      ],
    }),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const first = canvas.getByText('팀원F');
    const second = canvas.getByText('남궁현');

    await expect(canvasElement.querySelectorAll('.border-line-normal-assistive')).toHaveLength(2);

    // 가로가 아니라 세로로 쌓인다 — 좌변이 같고 둘째 줄이 아래에 온다.
    await expect(second.getBoundingClientRect().left).toBeCloseTo(first.getBoundingClientRect().left, 1);
    await expect(second.getBoundingClientRect().top).toBeGreaterThan(first.getBoundingClientRect().bottom);

    // 1줄 행의 52를 넘겨 행이 자란다 — 아이콘 40보다 스택이 높아진 결과다.
    await expect(canvas.getByRole('button').getBoundingClientRect().height).toBeGreaterThan(52);
  },
};

/** 담당자 미지정(빈 배열). 기본 아바타 + "담당자 없음" 문구가 선다 — 열 폭은 유지된다. */
export const UnassignedOwner: Story = {
  args: { kind: 'document', item: createFolderDocumentRow({ owners: [] }) },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByText('팀원F')).toBeNull();
    // 이름 대신 기본 프로필 폴백 아바타 + 문구가 선다 — 빈 칸이 되살아나면 여기서 잡힌다.
    await expect(canvas.getByText('담당자 없음')).toBeInTheDocument();
    await expect(canvasElement.querySelector('svg[viewBox="0 0 40 40"]')).not.toBeNull();
    await expect(canvasElement.querySelector('.border-line-normal-assistive')).not.toBeNull();

    await expect(canvas.getByText('2일 전').getBoundingClientRect().width).toBe(96);
  },
};

/** 두 표의 머리글 + 행 조합. 각 표가 자기 열 구성과 맞는지 좌표로 잰다. */
export const TableAlignment: Story = {
  args: { kind: 'folder', item: CHANNEL_FOLDER_ROW_FIXTURES[0] },
  render: () => (
    <div className="flex w-260 flex-col gap-6">
      <div data-testid="folder-table" className="flex flex-col gap-1">
        <FolderDocumentTableHeader kind="folder" />
        {CHANNEL_FOLDER_ROW_FIXTURES.slice(0, 2).map((row) => (
          <FolderDocumentRow key={row.id} kind="folder" item={row} />
        ))}
      </div>
      <div data-testid="document-table" className="flex flex-col gap-1">
        <FolderDocumentTableHeader kind="document" />
        {FOLDER_DOCUMENT_ROW_FIXTURES.slice(0, 1).map((row) => (
          <FolderDocumentRow key={row.id} kind="document" item={row} />
        ))}
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const folderTable = within(canvasElement.querySelector('[data-testid="folder-table"]') as HTMLElement);
    const documentTable = within(canvasElement.querySelector('[data-testid="document-table"]') as HTMLElement);
    const left = (element: Element) => element.getBoundingClientRect().left;

    // 폴더 표에는 담당자·상태 머리글이 없다 — 되살아나면 빈 열이 다시 생긴 것이다.
    await expect(folderTable.queryByText('담당자')).toBeNull();
    await expect(folderTable.queryByText('상태')).toBeNull();

    // 폴더 표: 메타가 96 한 칸으로 줄고 뺀 332는 이름 열이 흡수한다.
    // 마지막 열은 두 표 모두 우측 끝 96이라 같은 자리에 선다 — 화면을 오가도 열이 튀지 않는다.
    const folderActivity = folderTable.getByText('최근 활동');
    const documentActivity = documentTable.getByText('최근 활동');
    await expect(folderActivity.getBoundingClientRect().width).toBe(96);
    await expect(folderActivity.parentElement!.getBoundingClientRect().width).toBe(96);
    await expect(documentActivity.parentElement!.getBoundingClientRect().width).toBe(428);
    await expect(left(folderActivity)).toBeCloseTo(left(documentActivity), 1);

    // 각 표 안에서는 머리글과 행의 열이 맞는다.
    await expect(left(folderTable.getAllByText('2일 전')[0])).toBeCloseTo(left(folderActivity), 1);
    const ownerHeader = documentTable.getByText('담당자');
    await expect(left(documentTable.getByText('팀원F').parentElement!)).toBeCloseTo(left(ownerHeader), 1);
  },
};

/** 좁은 슬롯. 폭이 줄면 고정폭 열이 아니라 이름 열이 흡수하고 이름이 한 줄로 잘려야 한다. */
export const LongNameInNarrowSlot: Story = {
  args: {
    kind: 'document',
    item: createFolderDocumentRow({
      name: '결제 승인 실패 시 재시도 정책 및 PG사별 예외 처리와 고객 안내 문구 표준화 가이드 문서명 text text text',
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
    const row = canvas.getByRole('button');
    const slot = canvasElement.querySelector('div.w-200') as HTMLElement;
    const name = canvas.getByText(args.item.name);

    // 이름이 늘어나도 행은 슬롯을 넘지 않는다.
    await expect(row.getBoundingClientRect().width).toBeLessThanOrEqual(slot.getBoundingClientRect().width);
    await expect(row.scrollWidth).toBeLessThanOrEqual(row.clientWidth);

    // 고정폭 열은 좁아져도 그대로다 — 줄어드는 쪽은 이름 열이어야 한다.
    await expect(canvas.getByText('2일 전').getBoundingClientRect().width).toBe(96);

    // truncate가 빠지면 줄바꿈으로 폭은 지키면서 행 높이가 자란다 — 넘침 없음만으로는 부족하다.
    await expect(name.scrollWidth).toBeGreaterThan(name.clientWidth);
    await expect(name.getClientRects()).toHaveLength(1);
  },
};
