import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  WIKI_DOCUMENT_BREADCRUMBS,
  WIKI_DOCUMENT_FIXTURE,
  WIKI_DOCUMENT_LAYOUT_FIXTURE,
} from '../../fixtures/llmWikiDocumentFixtures';
import WikiDocumentNotPublished from './states/WikiDocumentNotPublished';
import WikiDocumentPageSkeleton from './states/WikiDocumentPageSkeleton';
import WikiDocumentPage from './WikiDocumentPage';

const meta = {
  title: 'Screens/LLM Wiki/DocumentPage',
  component: WikiDocumentPage,
  tags: ['autodocs'],
  args: {
    document: WIKI_DOCUMENT_FIXTURE,
    breadcrumbs: WIKI_DOCUMENT_BREADCRUMBS,
    onBreadcrumbClick: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=19035-134490',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '19035:134490',
      },
      viewport: { width: 1200, height: 1000 },
      states: [
        'default',
        'read-layout',
        'narrative-missing-fallback',
        'channel-root-document',
        'first-load',
        'not-published',
      ],
      reuseNotes: [
        'WikiPageHeader(detail)를 무수정 소비하고, 본문 타이포그래피는 공용 markdown-reading.css(.markdown-body.markdown-reading)를 쓴다 — 에디터와 같은 읽기 규격이라 새 타입 스케일을 만들지 않는다.',
        '경로 마디 조립·이름 join은 화면 밖(라우트 훅)에서 끝나고 이 화면은 받은 마디만 그린다.',
      ],
      dataNotes: [
        '픽스처는 ArtifactDocumentResponse를 매퍼에 통과시킨 모양이다(계약 확인 2026-08-23, CAM-296).',
        'layout이 있으면 그 순서·이름으로 읽고, 비면 blocks 순서로 읽는다 — 양식 없는 kind와 layout을 싣지 않는 구서버가 후자다.',
        'layout은 표시 순서와 이름만 정한다. 본문·근거의 원천은 여전히 blocks이고 block_index는 blocks 자리 그대로다(재번호 없음).',
        '머리말 세 블록의 제목은 서버가 양식 라벨(한 줄 요약·원하는 결과·요청 배경)로 바꿔 layout에 싣는다 — 블록의 heading은 section key라 화면에 내지 않는다.',
        '미지 item_kind는 매퍼가 떨궈 렌더하지 않는다 — 종류가 늘어도 화면이 깨지지 않는다.',
        '본문은 narrative가 정본이고 없으면 body로 폴백한다 — 검토 큐 diff와 같은 규칙.',
        '블록 근거(sources)는 계약에 있으나 렌더하지 않는다 — 8/5 시안의 우측 근거 패널이 8/10 시안에서 사라졌다.',
        '문서는 열람 전용이다 — 편집 진입점·저장 경로를 두지 않는다(MVP 제외).',
        '작성자·유형/상태 태그·아바타 그룹은 표시 시안이 없어 비운다. 최종 편집자(last_edited_by)는 계약에 있고 매퍼가 싣지만 이 화면에는 자리가 없다 — SNB 케밥 메타에만 쓴다.',
        '라우트 갈래는 넷이다 — isPending이면 골격(Loading), 미발행 404면 안내(Unpublished), 그 밖의 실패는 빈 화면, 나머지가 데이터 화면이다.',
        '미발행 안내의 문구·조립은 시안이 없어 자작이다. 그 밖의 조회 실패는 여전히 시안이 없어 토스트만 뜬다.',
      ],
      layoutNotes: [
        '본문 폭은 max-w-260, 패딩 px-6·py-9 — 헤더는 폭을 흡수하고 본문만 가운데로 모인다.',
        '표 항목은 markdown-reading.css의 표 규칙(.table-wrapper + table/th/td)을 그대로 쓴다 — 라벨이 행 머리(th scope="row")이고 값이 td다. 표 시안이 없어 새 시각을 만들지 않았다.',
        '자리표시 항목은 제목 + 문구를 본문과 같은 타이포로 낸다 — 흐림·배지 같은 구분 표시는 시안이 없어 넣지 않았다.',
      ],
      interactionNotes: [
        '검토큐 헤더의 "미리보기"가 이 화면의 도달 경로다 — 발행본을 새 탭(/llm-wiki/{artifactId})으로 연다. 제안본 미리보기 표면은 없다.',
        '아직 발행된 판이 없는 문서를 열면 Unpublished 안내가 뜨고, 버튼이 검토 큐로 그 문서의 안건을 골라 보낸다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiDocumentPage>;

export default meta;
type Story = StoryObj<typeof WikiDocumentPage>;

/** 발행판을 읽는 기본 화면. 경로(채널 > 폴더 > 문서)·발행 시각·블록 3덩이가 함께 선다. */
export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    // 경로의 마지막 마디가 현재 페이지다.
    const currentCrumb = canvasElement.querySelector('[aria-current="page"]')!;
    await expect(currentCrumb).toHaveTextContent('결제 실패 대응 가이드');

    await expect(canvas.getByRole('heading', { level: 1, name: '결제 실패 대응 가이드' })).toBeInTheDocument();
    await expect(canvas.getByText('23시간 전')).toBeInTheDocument();

    // 블록 heading은 본문 안 제목이라 h1과 층위가 갈린다.
    await expect(canvas.getByRole('heading', { level: 2, name: '현황' })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 2, name: '대응 절차' })).toBeInTheDocument();

    // layout이 빈 응답(양식 없는 종류·구서버)은 blocks 순서 그대로 읽는다 — 표도 자리표시도 없다.
    const headings = canvas.getAllByRole('heading', { level: 2 }).map((node) => node.textContent);
    await expect(headings).toEqual(['현황', '대응 절차', 'PG사별 재시도 간격']);
    await expect(canvasElement.querySelector('table')).toBeNull();

    // 산문이 있으면 산문만 나간다 — 값 표기는 화면에 실리지 않는다.
    await expect(canvas.getByText(/결제 실패율이 3.2%까지 올랐고/)).toBeInTheDocument();
    await expect(canvas.queryByText(/failure_rate = 3.2%/)).toBeNull();

    // 산문이 없는 블록만 값 표기로 폴백한다.
    await expect(canvas.getByText(/toss = 30s/)).toBeInTheDocument();

    // 값 표기의 줄바꿈이 접히면 항목이 한 줄로 붙는다.
    const fallback = canvas.getByText(/toss = 30s/);
    await expect(getComputedStyle(fallback).whiteSpace).toBe('pre-wrap');

    // 열람 전용 — 편집 진입점도 입력 자리도 없다.
    await expect(canvas.queryByRole('textbox')).toBeNull();
    await expect(canvasElement.querySelector('[contenteditable="true"]')).toBeNull();
    await expect(canvas.queryByRole('link')).toBeNull();

    // 이전 마디는 버튼이고 클릭이 밖으로 나간다.
    await userEvent.click(canvas.getByRole('button', { name: '결제' }));
    await expect(args.onBreadcrumbClick).toHaveBeenCalledWith({ kind: 'channel', label: '결제' }, 0);
  },
};

/**
 * 읽기 양식이 있는 문서 종류. 표시 순서·제목이 layout에서 오고, 표 항목과 자리표시가 함께 선다.
 * blocks는 재배치되지 않는다 — 순서를 바꾸는 것은 화면뿐이다.
 */
export const WithLayout: Story = {
  args: {
    document: WIKI_DOCUMENT_LAYOUT_FIXTURE,
    breadcrumbs: [
      { kind: 'channel', label: 'VOC' },
      { kind: 'document', label: WIKI_DOCUMENT_LAYOUT_FIXTURE.title },
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 제목은 양식 라벨이다 — 블록의 heading(section key)은 화면에 나가지 않는다.
    await expect(canvas.getByRole('heading', { level: 2, name: '한 줄 요약' })).toBeInTheDocument();
    await expect(canvas.queryByRole('heading', { name: 'one_line_summary' })).toBeNull();
    await expect(canvas.queryByRole('heading', { name: 'request_status' })).toBeNull();

    // 저장 순서(최근 보고 = 3번)보다 양식 순서(요청 상태 = 4번)가 앞선다.
    const headings = canvas.getAllByRole('heading', { level: 2 }).map((node) => node.textContent);
    await expect(headings.indexOf('요청 상태')).toBeLessThan(headings.indexOf('최근 보고'));
    await expect(headings.slice(0, 3)).toEqual(['한 줄 요약', '원하는 결과', '최근 보고']);

    const details = canvasElement.querySelector('dl')!;
    await expect(within(details).getByText('요청 배경')).toBeInTheDocument();
    await expect(within(details).getByText('요청 상태')).toBeInTheDocument();
    await expect(within(details).getByText('매월 결제 내역을 손으로 옮겨 적고 있다.')).toBeInTheDocument();
    await expect(within(details).getByText('검토 중이다.')).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 2, name: '사용 상황' })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 2, name: '지원 상태' })).toBeInTheDocument();

    // 자리표시: 가리킬 블록이 없어도 양식이 자리를 남긴다.
    await expect(canvas.getByRole('heading', { level: 2, name: '우회 방법' })).toBeInTheDocument();
    await expect(canvas.getByText('없음')).toBeInTheDocument();

    // 열람 전용은 양식이 있어도 그대로다.
    await expect(canvas.queryByRole('textbox')).toBeNull();
  },
};

/** 산문이 없던 옛 판. 블록 전부가 값 표기로 폴백한다. */
export const NarrativeMissing: Story = {
  args: {
    document: {
      ...WIKI_DOCUMENT_FIXTURE,
      blocks: WIKI_DOCUMENT_FIXTURE.blocks.map((block) => ({ ...block, narrative: null })),
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText(/failure_rate = 3.2%/)).toBeInTheDocument();
    await expect(canvas.queryByText(/결제 실패율이 3.2%까지 올랐고/)).toBeNull();

    // 폴백해도 블록 heading은 그대로 남는다.
    await expect(canvas.getByRole('heading', { level: 2, name: '현황' })).toBeInTheDocument();
  },
};

export const LongTimelineText: Story = {
  args: {
    document: {
      ...WIKI_DOCUMENT_LAYOUT_FIXTURE,
      blocks: WIKI_DOCUMENT_LAYOUT_FIXTURE.blocks.map((block) =>
        block.blockIndex === 5
          ? {
              ...block,
              narrative:
                'LLM Wiki 권한 관련해서 희망 사항이 있는데, RBAC 기반으로 문서 관리가 되면 좋겠다는 의견이에요. 담당자는 검토 흐름과 현재 지원 상태를 한 화면에서 확인할 수 있어야 해요. 이 문장은 한국어 긴 본문이 좁은 폭에서도 단어 단위로 자연스럽게 줄바꿈되는지 확인하기 위한 표본입니다.',
            }
          : block,
      ),
    },
  },
  play: async ({ canvasElement }) => {
    const text = within(canvasElement).getByText(/RBAC 기반으로 문서 관리가 되면 좋겠다는 의견이에요/);
    await expect(text.scrollWidth).toBeLessThanOrEqual(text.clientWidth);
    await expect(getComputedStyle(text).wordBreak).toBe('keep-all');
  },
};

/** 폴더 없이 채널 루트에 놓인 문서. 경로 마디가 하나 줄어든다. */
export const ChannelRootDocument: Story = {
  args: {
    document: { ...WIKI_DOCUMENT_FIXTURE, folderId: null },
    breadcrumbs: WIKI_DOCUMENT_BREADCRUMBS.filter((crumb) => crumb.kind !== 'folder'),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.queryByRole('button', { name: '장애 대응' })).toBeNull();
    await expect(canvas.getByRole('button', { name: '결제' })).toBeInTheDocument();
    await expect(canvasElement.querySelector('[aria-current="page"]')).toHaveTextContent('결제 실패 대응 가이드');
  },
};

/** 문서를 기다리는 동안. 라우트 조건은 isPending 하나이고, 화면 대신 골격이 선다. */
export const Loading: Story = {
  render: () => <WikiDocumentPageSkeleton />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('status', { name: '문서 불러오는 중' })).toBeInTheDocument();
    // 골격은 제목 자리를 잡을 뿐 제목을 쓰지 않는다 — 로딩과 데이터 화면이 같은 글자를 내면 안 된다.
    await expect(canvas.queryByRole('heading', { level: 1 })).toBeNull();
  },
};

/**
 * 미발행 문서(404 ARTIFACT_NOT_PUBLISHED). 라우트가 안내 화면으로 갈리고 실패 토스트는 뜨지 않는다.
 * 버튼 콜백 어서션은 안내 컴포넌트 스토리에 있다.
 */
export const Unpublished: Story = {
  render: () => <WikiDocumentNotPublished onOpenReviewQueue={fn()} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('아직 첫 판이 발행되지 않았어요')).toBeInTheDocument();
    await expect(canvas.getByText('첫 변경안이 검토를 기다리고 있어요')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '검토 큐에서 보기' })).toBeInTheDocument();

    // 발행판이 없으니 제목·본문 자리는 서지 않고, 경로 마디도 풀 수 없다.
    await expect(canvas.queryByRole('heading')).toBeNull();
    await expect(canvasElement.querySelector('[aria-current="page"]')).toBeNull();
  },
};
