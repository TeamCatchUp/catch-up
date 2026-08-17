import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  FOLDER_DOCUMENT_ROW_FIXTURES,
  WIKI_CHANNEL_FIXTURE,
  WIKI_FOLDER_FIXTURE,
} from '../../fixtures/llmWikiSpaceFixtures';
import WikiFolderPage from './WikiFolderPage';

const meta = {
  title: 'Screens/LLM Wiki/FolderPage',
  component: WikiFolderPage,
  tags: ['autodocs'],
  args: {
    channel: WIKI_CHANNEL_FIXTURE,
    folder: WIKI_FOLDER_FIXTURE,
    documentRows: FOLDER_DOCUMENT_ROW_FIXTURES,
    authorName: '팀원G',
    pageSize: 20,
    currentPage: 1,
    totalPages: 5,
    onPageChange: fn(),
    onDocumentClick: fn(),
    onBreadcrumbClick: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17762-104787',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17762:104787',
      },
      viewport: { width: 1200, height: 1440 },
      states: ['default'],
      reuseNotes: [
        '채널 페이지와 같은 조립이다 — WikiSpaceTitleBlock·WikiSpaceTableFooter·FolderDocumentRow(kind=document)·DashboardDocumentTableHeader 공유.',
        'breadcrumb는 채널>폴더 2마디로 끝난다(폴더 depth 1 백엔드 계약) — 채널 마디만 클릭 가능.',
      ],
      dataNotes: [
        '폴더 내 문서 목록 API가 없다(wiki 라우터 전수 — 감사 8/13 부록) — 행 데이터 전체가 협상 대상 mock이다.',
        '시안 행 텍스트는 "폴더명 text…" placeholder 잔재라 카피 확인 대상 — 픽스처는 문서명으로 채운다.',
        '빈 폴더·로딩·에러·404 스토리는 만들지 않는다 — 디자인 MISSING 유지.',
      ],
      tokenNotes: ['채널 페이지와 동일 매핑 — ChannelPage 스토리 tokenNotes 참조.'],
      layoutNotes: ['채널 페이지와 동일 산술(px-20·py-9·gap-9·gap-8) — 기하 어서션은 ChannelPage 스토리가 잰다.'],
    }),
  },
} satisfies Meta<typeof WikiFolderPage>;

export default meta;
type Story = StoryObj<typeof WikiFolderPage>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // breadcrumb 2마디: 채널 마디는 버튼, 폴더 마디가 현재 페이지다.
    const currentCrumb = canvasElement.querySelector('[aria-current="page"]')!;
    await expect(currentCrumb).toHaveTextContent('승인·실패 처리');
    await userEvent.click(canvas.getByRole('button', { name: '결제' }));
    await expect(args.onBreadcrumbClick).toHaveBeenCalledWith({ kind: 'channel', label: '결제' }, 0);

    await expect(canvas.getByRole('heading', { level: 1, name: '승인·실패 처리' })).toBeInTheDocument();
    await expect(canvas.getByText('작성자')).toBeInTheDocument();

    // 문서 행 3개 — 선두 아이콘은 문서다(file_filled 루트 fill=none — folder_filled는 currentColor).
    for (const row of FOLDER_DOCUMENT_ROW_FIXTURES) {
      await expect(canvas.getByText(row.name)).toBeInTheDocument();
    }
    const firstRow = canvas.getByRole('button', { name: /재시도 정책/ });
    await expect(firstRow.querySelector('svg')?.getAttribute('fill')).toBe('none');

    await userEvent.click(firstRow);
    await expect(args.onDocumentClick).toHaveBeenCalledWith('doc-payment-retry');

    // 푸터 상호작용은 공유 컴포넌트라 페이지 넘김만 재확인한다.
    await userEvent.click(canvas.getByRole('button', { name: '3' }));
    await expect(args.onPageChange).toHaveBeenCalledWith(3);
  },
};
