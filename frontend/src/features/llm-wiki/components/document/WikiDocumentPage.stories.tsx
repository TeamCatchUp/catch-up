import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { WIKI_DOCUMENT_BREADCRUMBS, WIKI_DOCUMENT_FIXTURE } from '../../fixtures/llmWikiDocumentFixtures';
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17735-186169',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17735:186169',
      },
      viewport: { width: 1200, height: 1000 },
      states: ['default', 'narrative-missing-fallback', 'channel-root-document'],
      reuseNotes: [
        'WikiPageHeader(detail)를 무수정 소비하고, 본문 타이포그래피는 공용 markdown.css(.markdown-body)를 쓴다 — 에디터와 같은 읽기 규격이라 새 타입 스케일을 만들지 않는다.',
        '경로 마디 조립·이름 join은 화면 밖(라우트 훅)에서 끝나고 이 화면은 받은 마디만 그린다.',
      ],
      dataNotes: [
        '픽스처는 ArtifactDocumentResponse를 매퍼에 통과시킨 모양이다(계약 확인 2026-08-19).',
        '본문은 narrative가 정본이고 없으면 body로 폴백한다 — 검토 큐 diff와 같은 규칙.',
        '블록 근거(sources)는 계약에 있으나 렌더하지 않는다 — 8/5 시안의 우측 근거 패널이 8/10 시안에서 사라졌다.',
        '문서는 열람 전용이다 — 편집 진입점·저장 경로를 두지 않는다(MVP 제외).',
        '작성자·유형/상태 태그·아바타 그룹은 대응 필드가 없어 비운다. 시안의 "Created by"는 발행 시각만 남겼다.',
        '로딩·에러·미발행(404 ARTIFACT_NOT_PUBLISHED) 스토리는 만들지 않는다 — 디자인 MISSING 유지.',
      ],
      layoutNotes: [
        '본문 폭은 max-w-260, 패딩 px-6·py-9 — 헤더는 폭을 흡수하고 본문만 가운데로 모인다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiDocumentPage>;

export default meta;
type Story = StoryObj<typeof WikiDocumentPage>;

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
