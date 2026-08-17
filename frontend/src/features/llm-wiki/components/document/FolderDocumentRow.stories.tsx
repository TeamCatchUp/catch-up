import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  CHANNEL_FOLDER_ROW_FIXTURES,
  createFolderDocumentRow,
  FOLDER_DOCUMENT_ROW_FIXTURES,
} from '../../fixtures/llmWikiSpaceFixtures';
import { DashboardDocumentTableHeader } from './DashboardDocumentRow';
import FolderDocumentRow from './FolderDocumentRow';

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
      states: ['folder-row', 'document-row', 'table-alignment', 'long-name-narrow-slot'],
      reuseNotes: [
        '열 기하는 대시보드 표와 동일 실측이라 DASHBOARD_DOCUMENT_TABLE_SHELL·META_GRID 상수를 공유한다 — 헤더도 DashboardDocumentTableHeader 그대로.',
        '담당자 아바타·상태 배지·최근 활동 열은 DashboardDocumentRow와 같은 조합(공용 Avatar small 25 + line-assistive 링, DocumentStatusBadge md).',
        'folder_filled·file_filled 에셋 재사용 — 신규 export 없음.',
      ],
      dataNotes: [
        '2026-08-13 재실측(채널 17724:185191·폴더 17762:104787): 8/5의 VOC·고객사 아이콘 쌍 행이 담당자·상태·최근 활동 열로 교체됐다.',
        '행 상태는 시안에 도시된 검토 완료만 픽스처로 쓴다 — 다른 상태 행·폴더 배지 집계 의미는 미도시(디자이너 질문 유지).',
        '담당자 이름·이미지, 최근 활동은 목록 API 미동봉(협상 대상) — 감사 8/13 부록 참조.',
      ],
      tokenNotes: [
        '이름 #33363D = text-text-normal-normal + heading(sb)/small. 아이콘 셸 #F7F7F8 = bg-fill-normal-strong, 아이콘 #B1B8BE = text-icon-normal-alternative.',
        '최근 활동 #6D7882 = text-text-normal-alternative + body(md)/small 우측 정렬 — 대시보드 행과 동일 매핑.',
      ],
      layoutNotes: [
        '경로 줄이 없는 1줄 행이라 행 높이 52는 결과값(6+40+6)이다 — h-*를 두지 않는다.',
        '폭 흡수는 이름 열 하나뿐이고 메타 그리드 140/160/96·gap 16은 고정 — 검산 6+564+36+140+16+160+16+96+6=1040.',
      ],
    }),
  },
} satisfies Meta<typeof FolderDocumentRow>;

export default meta;
type Story = StoryObj<typeof FolderDocumentRow>;

// 선두 아이콘 구분: folder_filled는 루트 fill="currentColor", file_filled는 fill="none" — viewBox가 같아 fill로 가른다.
const leadingIconFill = (row: HTMLElement) => row.querySelector('svg')?.getAttribute('fill');

export const FolderRow: Story = {
  args: { kind: 'folder', item: CHANNEL_FOLDER_ROW_FIXTURES[0] },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('승인·실패 처리')).toBeInTheDocument();
    await expect(canvas.getByText('팀원F')).toBeInTheDocument();
    await expect(canvas.getByText('검토 완료')).toBeInTheDocument();
    await expect(canvas.getByText('2일 전')).toBeInTheDocument();

    const row = canvas.getByRole('button');
    await expect(leadingIconFill(row)).toBe('currentColor');

    // 고정폭 열이 살아 있는지 — 무너지면 행끼리 열이 어긋난다.
    await expect(canvas.getByText('2일 전').getBoundingClientRect().width).toBe(96);

    await userEvent.click(row);
    await expect(args.onClick).toHaveBeenCalledWith('folder-approval-failure');
  },
};

export const DocumentRow: Story = {
  args: { kind: 'document', item: FOLDER_DOCUMENT_ROW_FIXTURES[0] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('결제 승인 실패 시 재시도 정책')).toBeInTheDocument();
    await expect(leadingIconFill(canvas.getByRole('button'))).toBe('none');
  },
};

/** 대시보드 헤더 + 폴더 행 + 문서 행 조합. 세 표가 같은 열 상수를 쓰는지 좌표로 잰다. */
export const TableAlignment: Story = {
  args: { kind: 'folder', item: CHANNEL_FOLDER_ROW_FIXTURES[0] },
  render: () => (
    <div className="flex w-260 flex-col gap-1">
      <DashboardDocumentTableHeader />
      {CHANNEL_FOLDER_ROW_FIXTURES.slice(0, 2).map((row) => (
        <FolderDocumentRow key={row.id} kind="folder" item={row} />
      ))}
      {FOLDER_DOCUMENT_ROW_FIXTURES.slice(0, 1).map((row) => (
        <FolderDocumentRow key={row.id} kind="document" item={row} />
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 담당자 열: 헤더 셀 좌변 == 폴더 행·문서 행의 담당자 셀 좌변.
    // '팀원F'은 폴더 행(0)과 문서 행(1)에 하나씩 있다 — 두 kind를 같은 이름으로 잰다.
    const ownerHeader = canvas.getByText('담당자');
    for (const ownerLabel of canvas.getAllByText('팀원F')) {
      await expect(ownerLabel.parentElement!.getBoundingClientRect().left).toBeCloseTo(
        ownerHeader.getBoundingClientRect().left,
        1,
      );
    }

    // 최근 활동 열: 우측 정렬 열이라 우변으로 잰다.
    const activityHeader = canvas.getByText('최근 활동');
    await expect(canvas.getByText('2일 전').getBoundingClientRect().right).toBeCloseTo(
      activityHeader.getBoundingClientRect().right,
      1,
    );
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
