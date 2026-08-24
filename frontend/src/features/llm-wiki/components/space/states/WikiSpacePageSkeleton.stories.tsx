import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { CHANNEL_FOLDER_ROW_FIXTURES, FOLDER_DOCUMENT_ROW_FIXTURES } from '../../../fixtures/llmWikiSpaceFixtures';
import FolderDocumentRow, { FolderDocumentTableHeader } from '../../document/FolderDocumentRow';
import WikiSpacePageSkeleton from './WikiSpacePageSkeleton';

const meta = {
  title: 'Screens/LLM Wiki/States/WikiSpacePageSkeleton',
  component: WikiSpacePageSkeleton,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      viewport: { width: 1200, height: 900 },
      states: ['document-first-load', 'folder-first-load', 'document-column-alignment', 'folder-column-alignment'],
      reuseNotes: [
        '표 골격은 대시보드와 공유하는 DocumentTableSkeleton이고, 표 머리글은 데이터 화면과 같은 FolderDocumentTableHeader를 그대로 쓴다.',
        '[8/24] 채널 화면 표가 담당자·상태 없는 2열이 되어 골격도 kind로 갈린다 — 채널 라우트는 folder, 폴더 라우트는 document를 넘긴다.',
      ],
      dataNotes: [
        '채널·폴더 화면이 채널 목록을 기다리는 동안 서는 골격이다 — 이름을 아직 몰라 breadcrumb 헤더와 제목까지 자리만 남긴다.',
        '로딩 시안이 없어 전량 자작이다(사용자 확정). 에러·미존재는 로딩이 아니므로 이 골격이 서지 않는다 — 에러는 토스트, 없는 폴더는 notFound다.',
        '푸터는 그리지 않는다 — 쪽 수를 아직 모르고 표 아래라 뒤이어 붙어도 위쪽이 밀리지 않는다.',
      ],
      layoutNotes: [
        '헤더 h-13·커버 h-50·본문 px-20 py-9·제목↔표 gap-9는 데이터 화면과 같은 값이다 — 로드 후 표가 제자리에 서야 한다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiSpacePageSkeleton>;

export default meta;
type Story = StoryObj<typeof WikiSpacePageSkeleton>;

/** 폴더 화면(문서 표) 골격 — 메타 3열이 전부 선다. */
export const Default: Story = {
  args: { kind: 'document' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('status', { name: '불러오는 중' })).toBeInTheDocument();
    // 표 머리글은 골격 단계에서도 실물이다 — 열 기준이 여기서 나온다.
    await expect(canvas.getByText('담당자')).toBeInTheDocument();
    await expect(canvas.getByText('최근 활동')).toBeInTheDocument();
  },
};

/** 채널 화면(폴더 표) 골격 — 담당자·상태 없이 최근 활동 한 칸만 선다. */
export const FolderVariant: Story = {
  args: { kind: 'folder' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('최근 활동')).toBeInTheDocument();
    // 폴더 표에 없는 열이 골격에 되살아나면 로드 순간 열이 튄다.
    await expect(canvas.queryByText('담당자')).toBeNull();
    await expect(canvas.queryByText('상태')).toBeNull();

    const status = canvas.getByRole('status', { name: '목록 불러오는 중' });
    const meta = (status.firstElementChild as HTMLElement).lastElementChild as HTMLElement;
    await expect(meta.children).toHaveLength(1);
  },
};

/** 골격 행과 문서 데이터 행을 같은 폭에 세워 열이 어긋나지 않는지 좌표로 잰다. */
export const ColumnAlignment: Story = {
  args: { kind: 'document' },
  render: () => (
    <div className="flex flex-col">
      <WikiSpacePageSkeleton kind="document" />
      <div className="flex flex-col px-20">
        <FolderDocumentTableHeader kind="document" />
        <FolderDocumentRow kind="document" item={FOLDER_DOCUMENT_ROW_FIXTURES[0]} />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const status = canvas.getByRole('status', { name: '목록 불러오는 중' });

    // 메타 셀 폭 428 = 140+16+160+16+96 — 데이터 행과 같아야 로드 후 열이 움직이지 않는다.
    const skeletonMeta = (status.firstElementChild as HTMLElement).lastElementChild as HTMLElement;
    const dataMeta = canvas.getByRole('button', { name: /결제 승인 실패/ }).lastElementChild as HTMLElement;
    await expect(skeletonMeta.getBoundingClientRect().width).toBe(428);
    await expect(skeletonMeta.getBoundingClientRect().left).toBeCloseTo(dataMeta.getBoundingClientRect().left, 1);
  },
};

/** 폴더 표 골격도 같은 검산 — 메타 셀이 최근 활동 96 한 칸으로 준다. */
export const FolderColumnAlignment: Story = {
  args: { kind: 'folder' },
  render: () => (
    <div className="flex flex-col">
      <WikiSpacePageSkeleton kind="folder" />
      <div className="flex flex-col px-20">
        <FolderDocumentTableHeader kind="folder" />
        <FolderDocumentRow kind="folder" item={CHANNEL_FOLDER_ROW_FIXTURES[0]} />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const status = canvas.getByRole('status', { name: '목록 불러오는 중' });

    const skeletonMeta = (status.firstElementChild as HTMLElement).lastElementChild as HTMLElement;
    const dataMeta = canvas.getByRole('button', { name: /승인·실패 처리/ }).lastElementChild as HTMLElement;
    await expect(skeletonMeta.getBoundingClientRect().width).toBe(96);
    await expect(skeletonMeta.getBoundingClientRect().left).toBeCloseTo(dataMeta.getBoundingClientRect().left, 1);
  },
};
