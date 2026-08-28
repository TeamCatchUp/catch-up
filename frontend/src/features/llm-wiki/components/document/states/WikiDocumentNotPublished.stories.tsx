import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import WikiDocumentNotPublished from './WikiDocumentNotPublished';

const meta = {
  title: 'Screens/LLM Wiki/States/WikiDocumentNotPublished',
  component: WikiDocumentNotPublished,
  tags: ['autodocs'],
  args: { onOpenReviewQueue: fn() },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      viewport: { width: 1200, height: 900 },
      states: ['not-published'],
      reuseNotes: [
        '일러스트·문구 타이포는 대시보드 빈 표(DocumentTableEmptyState)의 자산을 그대로 쓴다 — 새 일러스트를 만들지 않았다.',
        '버튼은 공용 Button의 box-outline-gray/md — 온보딩 실패 안내의 액션과 같은 규격이다.',
      ],
      dataNotes: [
        '문구·조립은 시안이 없어 전량 자작이다(제목·보조 문구·버튼 라벨).',
        '한 번도 발행되지 않은 문서(GET /wiki/artifacts/{id}가 404 ARTIFACT_NOT_PUBLISHED)만 이 화면을 받는다 — 그 밖의 실패는 여전히 토스트다.',
        '이 404는 조회 실패 토스트에서 빠진다 — 정상 경로라 안내 화면 하나로 족하다.',
      ],
      layoutNotes: [
        '헤더는 마디 없이 셸(h-13 + 아래 선)만 남는다 — 경로 이름의 공급원이 404가 난 문서 응답이라 마디를 풀 수 없다.',
        '골격·데이터 화면과 같은 헤더 높이라 로드 결과가 갈려도 위쪽이 움직이지 않는다.',
      ],
      interactionNotes: [
        '버튼은 /llm-wiki/review?artifactId={id}로 간다 — 검토 큐가 그 문서의 계류 안건을 미리 고른다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiDocumentNotPublished>;

export default meta;
type Story = StoryObj<typeof WikiDocumentNotPublished>;

export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('아직 첫 판이 발행되지 않았어요')).toBeInTheDocument();
    await expect(canvas.getByText('첫 변경안이 검토를 기다리고 있어요')).toBeInTheDocument();

    // 빈 표 안내와 같은 일러스트 에셋·크기다 — 새로 그린 것이 아니다.
    const illustration = canvasElement.querySelector('svg') as SVGSVGElement;
    const box = illustration.getBoundingClientRect();
    // 높이는 뷰포트에 따라 서브픽셀로 떨어져 반올림해 잰다
    await expect(box.width).toBe(64);
    await expect(Math.round(box.height)).toBe(55);

    // 경로 마디는 없고 헤더 셸만 남는다.
    await expect(canvasElement.querySelector('[aria-current="page"]')).toBeNull();

    await userEvent.click(canvas.getByRole('button', { name: '검토 큐에서 보기' }));
    await expect(args.onOpenReviewQueue).toHaveBeenCalledTimes(1);
  },
};
