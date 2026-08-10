import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import ReviewNeededTag from './ReviewNeededTag';

const meta = {
  title: 'Compositions/LLM Wiki/Header/ReviewNeededTag',
  component: ReviewNeededTag,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17942-91620',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17942:91620',
      },
      viewport: { width: 200, height: 80 },
      states: ['review-needed'],
      reuseNotes: [
        '색은 shared Badge의 violet 변형(bg-accent-violet-neutral / text-accent-violet-default)이 Figma와 그대로 일치해 재사용했고, 기하만 덮었다 — DocumentStatusBadge가 success 변형에 대해 한 것과 같은 방식이다.',
        'icon/dash-circle(1880:9313)은 리포에 이미 있던 자산이다. 소비처가 0곳이었고 stroke="#464C53"이 하드코드돼 있어 currentColor로 정규화했다 — 리포의 다른 아이콘 관례와 같아졌고 파급은 없다.',
      ],
      dataNotes: [
        'DocumentStatusBadge("검토 완료")와 합치지 않는다. Figma 계보가 다르다 — 이쪽은 Tag 세트(452:2178)의 type=purple, 저쪽은 Badge 계열이고 기하도 radius 6 vs 8 · padding 2/6 vs 4/8 · 아이콘 18 vs 20으로 갈린다.',
        '확정된 태그는 "검토 필요" 1종뿐이라 라벨·색을 props로 열지 않았다(배지 발명 금지 계약). 다른 유형이 시안에 등장하면 그때 축을 연다.',
        '이 태그는 문서 status 값과 아직 연결돼 있지 않다 — 검토큐 문서 헤더 시안에만 나타나고, DocumentStatus에 대응 값이 없다. 헤더는 이 컴포넌트를 slot으로 받으므로 연결 지점은 조립 단계의 선택이다.',
      ],
      tokenNotes: [
        '배경 #F0ECFE = bg-accent-violet-neutral, 글자·아이콘 #6541F2 = text-accent-violet-default.',
        'radius 6 = rounded-md2, padding 2/6 = py-0.5 px-1.5, gap 4 = gap-1, body(md)/xsmall = text-body-xsmall, 아이콘 18 = size-4.5.',
      ],
      layoutNotes: [
        'Figma 태그는 hug이라 폭을 고정하지 않는다. 높이도 결과값이다(py 2 + 라인박스 19.5 + py 2).',
      ],
    }),
  },
} satisfies Meta<typeof ReviewNeededTag>;

export default meta;
type Story = StoryObj<typeof ReviewNeededTag>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const tag = canvas.getByText('검토 필요');

    await expect(tag).toBeInTheDocument();

    // shared Badge 기본값은 rounded-full이다. tailwind-merge가 이 덮어쓰기를 놓치면
    // 알약 모양으로 조용히 되돌아가므로 Figma의 radius 6을 직접 못박는다.
    await expect(getComputedStyle(tag).borderRadius).toBe('6px');

    const icon = tag.querySelector('svg');
    await expect(icon).not.toBeNull();
    await expect(icon).toHaveAttribute('aria-hidden');
    await expect(icon!.getBoundingClientRect().width).toBe(18);

    // 원본 export는 stroke="#464C53"이었다. 재export로 hex가 되살아나면 라이트 모드에서는
    // 우연히 비슷해 보이고 다크 모드에서만 어긋나므로, 계산색이 아니라 속성을 못박는다.
    await expect(icon!.querySelector('path')).toHaveAttribute('stroke', 'currentColor');
  },
};
