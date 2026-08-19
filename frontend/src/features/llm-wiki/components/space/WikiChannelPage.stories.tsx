import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { CHANNEL_FOLDER_ROW_FIXTURES, WIKI_CHANNEL_FIXTURE } from '../../fixtures/llmWikiSpaceFixtures';
import WikiChannelPage from './WikiChannelPage';

const meta = {
  title: 'Screens/LLM Wiki/ChannelPage',
  component: WikiChannelPage,
  tags: ['autodocs'],
  args: {
    channel: WIKI_CHANNEL_FIXTURE,
    folderRows: CHANNEL_FOLDER_ROW_FIXTURES,
    authorName: '팀원G',
    pageSize: 20,
    currentPage: 1,
    totalPages: 5,
    onPageChange: fn(),
    onFolderClick: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17724-185191',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17724:185191',
      },
      viewport: { width: 1200, height: 1440 },
      states: ['default', 'folder-rows-without-meta', 'long-names-narrow-viewport', 'empty'],
      reuseNotes: [
        'WikiPageHeader(detail·채널 1마디)·DashboardDocumentTableHeader·FolderDocumentRow·공용 Pagination을 조립만 한다 — 전부 무수정 소비.',
        '표 열은 대시보드와 같은 상수(DASHBOARD_DOCUMENT_META_GRID) 공유라 이 화면에서 재정의하지 않는다.',
        '빈 표는 대시보드가 쓰는 DocumentTableEmptyState를 문구만 갈아 재사용한다 — 일러스트·여백은 승인 시안 그대로다.',
      ],
      dataNotes: [
        '채널 mock은 ChannelListItemResponse 정합(WikiChannelListItem 소비) — 폴더 행의 담당자·상태·최근 활동과 작성자는 목록 API 미동봉(협상 대상, 감사 8/13 부록).',
        '실 라우트는 그 네 칸을 빈 값으로 넘긴다 — FolderRowsWithoutMeta가 그때의 표 모습이다.',
        '상단 200px 커버는 바탕색만 시안값이고 콘텐츠는 미정(사진 가능성) — 안은 비워 둔다. 페이지 크기 옵션 목록은 미도시라 정적 표시가 기본이다.',
        '헤더 우측 kebab 버튼은 두 시안에 있으나 동작 정의가 없어 렌더하지 않는다(actions 슬롯 비움) — 디자이너 질문.',
        '빈 채널 문구 "폴더가 없어요"는 시안 없이 지었다 — 대시보드 승인 문구 "문서가 없어요"의 어형을 그대로 따랐다(디자이너 확인 대상).',
        '로딩·에러 스토리는 만들지 않는다 — 디자인 MISSING 유지. 폴더는 채널 목록 응답에 전량 실려 와 빈 표는 폴더 0개일 때만 뜬다.',
      ],
      tokenNotes: [
        '채널명 #1E2124 = text-text-normal-strong + heading(sb)/xlarge. 작성자 라벨 #6D7882 = alternative, 이름 #464C53 = neutral, body(md)/xsmall.',
        '페이지 크기 컨트롤은 shared Select 트리거와 같은 조합(bg-fill-normal-normal + border-line-normal-neutral + rounded-lg).',
      ],
      layoutNotes: [
        '콘텐츠 패딩 px-20·py-9, 제목 블록↔표 gap-9, 표↔푸터 gap-8 — 1200 프레임 실측의 산술이고 폭 자체는 유동이다.',
        '긴 채널명은 truncate가 기본(시안에 줄바꿈 근거 없음) — 디자이너 제안으로 기록.',
      ],
    }),
  },
} satisfies Meta<typeof WikiChannelPage>;

export default meta;
type Story = StoryObj<typeof WikiChannelPage>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 헤더는 채널 1마디 breadcrumb이고, 그 마디가 현재 페이지다.
    const currentCrumb = canvasElement.querySelector('[aria-current="page"]')!;
    await expect(currentCrumb).toHaveTextContent('결제');

    await expect(canvas.getByRole('heading', { level: 1, name: '결제' })).toBeInTheDocument();
    await expect(canvas.getByText('작성자')).toBeInTheDocument();
    await expect(canvas.getByText('팀원G')).toBeInTheDocument();

    // 상단 커버(200) + py(36)만큼 제목 블록이 헤더에서 떨어진다.
    const banner = canvas.getByRole('banner');
    const titleRow = canvas.getByRole('heading', { level: 1 }).parentElement!;
    await expect(titleRow.getBoundingClientRect().top - banner.getBoundingClientRect().bottom).toBeCloseTo(236, 0);

    // 커버는 콘텐츠가 비어도 시안의 바탕색을 갖는다 — 투명이면 200px 공백으로 보인다.
    const cover = canvasElement.querySelector('header + div[aria-hidden]') as HTMLElement;
    await expect(cover.getBoundingClientRect().height).toBe(200);
    await expect(getComputedStyle(cover).backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
    await expect(cover).toBeEmptyDOMElement();

    // 표: 헤더 라벨과 폴더 행 4개.
    await expect(canvas.getByText('문서')).toBeInTheDocument();
    await expect(canvas.getByText('담당자')).toBeInTheDocument();
    for (const row of CHANNEL_FOLDER_ROW_FIXTURES) {
      await expect(canvas.getByText(row.name)).toBeInTheDocument();
    }

    // 행 선두 아이콘은 폴더다(folder_filled 루트 fill=currentColor — file_filled는 none).
    const firstRow = canvas.getByRole('button', { name: /승인·실패 처리/ });
    await expect(firstRow.querySelector('svg')?.getAttribute('fill')).toBe('currentColor');

    await userEvent.click(canvas.getByRole('button', { name: /환불/ }));
    await expect(args.onFolderClick).toHaveBeenCalledWith('folder-refund');

    // 푸터: 페이지 크기는 핸들러가 없으면 버튼이 아니다(옵션 시안 부재 — 죽은 버튼 방지).
    await expect(canvas.getByText('씩 나열')).toBeInTheDocument();
    await expect(canvas.getByText('20').closest('button')).toBeNull();

    await userEvent.click(canvas.getByRole('button', { name: '2' }));
    await expect(args.onPageChange).toHaveBeenCalledWith(2);
  },
};

/** 실 라우트가 넘기는 모습 — 폴더에 대응 필드가 없는 칸은 비고 작성자 줄은 서지 않는다. */
export const FolderRowsWithoutMeta: Story = {
  args: {
    authorName: undefined,
    folderRows: CHANNEL_FOLDER_ROW_FIXTURES.map(({ id, name }) => ({
      id,
      name,
      owners: [],
      status: '',
      lastActivityLabel: '',
    })),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 작성자 줄이 통째로 빠져도 제목 블록은 남는다.
    await expect(canvas.getByRole('heading', { level: 1, name: '결제' })).toBeInTheDocument();
    await expect(canvas.queryByText('작성자')).toBeNull();

    // 빈 칸이 열을 무너뜨리면 안 된다 — 머리글과 행의 메타 열 좌표가 계속 맞아야 한다.
    const header = canvas.getByText('최근 활동');
    const row = canvas.getByRole('button', { name: /승인·실패 처리/ });
    const meta = row.lastElementChild as HTMLElement;
    const activityCell = meta.lastElementChild as HTMLElement;
    await expect(activityCell.getBoundingClientRect().width).toBe(96);
    await expect(activityCell.getBoundingClientRect().left).toBeCloseTo(header.getBoundingClientRect().left, 0);
    await expect(canvas.queryByText('검토 완료')).toBeNull();
  },
};

/** 좁은 뷰포트 + 긴 이름. 고정폭 열은 지키고 이름 계열만 잘려야 한다. */
export const LongNamesInNarrowViewport: Story = {
  args: {
    channel: {
      ...WIKI_CHANNEL_FIXTURE,
      name: '결제·정산·환불 운영 정책과 PG 연동 이슈 대응을 모아 두는 아주 긴 채널 이름 표본',
    },
  },
  decorators: [
    (Story) => (
      <div className="w-225 overflow-hidden">
        <Story />
      </div>
    ),
  ],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const slot = canvasElement.querySelector('div.w-225') as HTMLElement;
    const heading = canvas.getByRole('heading', { level: 1 });

    // 채널명은 한 줄 truncate — 줄바꿈으로 제목 블록이 자라면 안 된다.
    await expect(heading.scrollWidth).toBeGreaterThan(heading.clientWidth);
    await expect(heading.getClientRects()).toHaveLength(1);

    // 행은 슬롯을 넘지 않고, 고정폭 열(최근 활동 96)은 그대로다.
    const firstRow = canvas.getByRole('button', { name: /승인·실패 처리/ });
    await expect(firstRow.getBoundingClientRect().width).toBeLessThanOrEqual(slot.getBoundingClientRect().width);
    await expect(canvas.getByText('2일 전').getBoundingClientRect().width).toBe(96);
  },
};

/** 폴더가 하나도 없는 채널. 표 헤더와 푸터는 남고 행 자리만 안내로 바뀐다. */
export const EmptyChannel: Story = {
  args: {
    channel: { ...WIKI_CHANNEL_FIXTURE, documentCount: 0, folders: [] },
    folderRows: [],
    totalPages: 1,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 문구는 대시보드 빈 표의 어형을 따르되 대상이 폴더다.
    await expect(canvas.getByText('폴더가 없어요')).toBeInTheDocument();
    await expect(canvas.queryByText('문서가 없어요')).toBeNull();

    // 제목 블록·표 헤더·푸터는 그대로다 — 빈 상태가 화면을 통째로 대체하지 않는다.
    await expect(canvas.getByRole('heading', { level: 1, name: '결제' })).toBeInTheDocument();
    await expect(canvas.getByText('최근 활동')).toBeInTheDocument();
    await expect(canvas.getByText('씩 나열')).toBeInTheDocument();

    // 폴더 행은 하나도 없다.
    for (const row of CHANNEL_FOLDER_ROW_FIXTURES) {
      await expect(canvas.queryByText(row.name)).toBeNull();
    }
  },
};
