import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import DashboardDocumentRow, { DashboardDocumentTableHeader } from '../DashboardDocumentRow';
import DocumentTableEmptyState from './DocumentTableEmptyState';

const meta = {
  title: 'Compositions/LLM Wiki/Document/DocumentTableEmptyState',
  component: DocumentTableEmptyState,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18234-49957',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18234:49957',
      },
      viewport: { width: 1040, height: 460 },
      states: ['default', 'with-header', 'custom-message'],
      reuseNotes: [
        '일러스트는 시안 프레임(18234:51036, 64x55)을 SVG 그대로 내려 커밋했다 — 임의 제작 아님.',
        '표 헤더는 DashboardDocumentTableHeader를 그대로 쓴다 — 빈 상태에서도 헤더가 남는 것이 시안이다.',
      ],
      dataNotes: [
        '2026-08-14 시안 도착으로 구현했다 — 그 전까지 대시보드 빈 상태는 MISSING이라 만들지 않던 항목이다(감사 금지 목록에서 해제).',
        '문구 "문서가 없어요"는 시안 실재값이다. 필터 결과 0건과 문서 0건을 문구로 가르지 않는다 — 시안이 하나뿐이다.',
        'message prop은 행 대상이 문서가 아닌 표(채널 페이지의 폴더 목록)를 위해 열었다 — 기본값은 시안 문구 그대로다.',
        '로딩·에러 상태는 여전히 MISSING이라 만들지 않는다.',
      ],
      tokenNotes: [
        '문구: body(md)/xsmall 13 + Text/Normal/Assistive #B1B8BE = text-body-xsmall·text-text-normal-assistive.',
        '일러스트는 자체 회색을 품은 에셋이라 색 클래스를 주지 않는다.',
      ],
      layoutNotes: [
        '상하 패딩 180 = py-45, 일러스트-문구 간격 20 = gap-5. 일러스트 64x55는 에셋 고유 크기다.',
        '폭을 갖지 않는다 — 표 자리가 폭을 주고 내용은 가운데 정렬된다.',
      ],
    }),
  },
} satisfies Meta<typeof DocumentTableEmptyState>;

export default meta;
type Story = StoryObj<typeof DocumentTableEmptyState>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('문서가 없어요')).toBeInTheDocument();

    // 일러스트는 시안 크기 그대로다.
    const illustration = canvasElement.querySelector('svg') as SVGSVGElement;
    const box = illustration.getBoundingClientRect();
    await expect(box.width).toBe(64);
    await expect(box.height).toBe(55);

    // 상하 180 여백이 이 빈 상태의 높이를 만든다 — 줄어들면 표가 폭삭 주저앉는다.
    const root = canvas.getByText('문서가 없어요').parentElement as HTMLElement;
    const style = getComputedStyle(root);
    await expect(style.paddingTop).toBe('180px');
    await expect(style.paddingBottom).toBe('180px');
    await expect(style.rowGap).toBe('20px');
  },
};

/** 표 안에 놓인 모습. 빈 상태에서도 헤더는 남고 행 자리만 비워진다. */
export const WithHeader: Story = {
  render: () => (
    <div className="flex w-260 flex-col">
      <DashboardDocumentTableHeader />
      <DocumentTableEmptyState />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 헤더 4열이 그대로 있어야 한다 — 빈 상태가 표를 통째로 지우지 않는다.
    await expect(canvas.getByText('문서')).toBeInTheDocument();
    await expect(canvas.getByText('담당자')).toBeInTheDocument();
    await expect(canvas.getByText('상태')).toBeInTheDocument();
    await expect(canvas.getByText('최근 활동')).toBeInTheDocument();

    await expect(canvas.getByText('문서가 없어요')).toBeInTheDocument();
    // 행은 하나도 없다.
    await expect(canvas.queryAllByRole('button')).toHaveLength(0);
  },
};

/** 행이 있으면 빈 상태가 나오지 않는다는 대비 — 조립 쪽 분기의 근거다. */
export const NotShownWithRows: Story = {
  render: () => (
    <div className="flex w-260 flex-col">
      <DashboardDocumentTableHeader />
      <DashboardDocumentRow
        document={{
          id: 'doc-sample',
          title: '표본 문서',
          breadcrumbs: [
            { kind: 'channel', label: '결제' },
            { kind: 'folder', label: '환불' },
          ],
          status: 'reviewed',
          owners: [{ userId: 1, displayName: '팀원F', profileImageUrl: null }],
          createdAt: '2024-09-02T01:00:00.000Z',
          lastActivityAt: '2024-12-15T06:00:00.000Z',
          lastActivityLabel: '3시간 전',
        }}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('표본 문서')).toBeInTheDocument();
    await expect(canvas.queryByText('문서가 없어요')).toBeNull();
  },
};

/** 문구만 갈아 끼운 모습 — 채널 페이지의 폴더 목록이 이 형태를 쓴다. */
export const CustomMessage: Story = {
  args: { message: '폴더가 없어요' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('폴더가 없어요')).toBeInTheDocument();
    await expect(canvas.queryByText('문서가 없어요')).toBeNull();

    // 문구만 바뀌고 일러스트·여백은 기본값과 같아야 한다.
    const illustration = canvasElement.querySelector('svg') as SVGSVGElement;
    await expect(illustration.getBoundingClientRect().width).toBe(64);
    const root = canvas.getByText('폴더가 없어요').parentElement as HTMLElement;
    await expect(getComputedStyle(root).paddingTop).toBe('180px');
  },
};
