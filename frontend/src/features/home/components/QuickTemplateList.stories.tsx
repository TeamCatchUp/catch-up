import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import { tipData } from '../constants/questionTips';
import QuickTemplateList from './QuickTemplateList';

const FIGMA_FILE_KEY = '7UwupbVvmHkElmP2OBJQio';
const NODE_ID = '17496:46091';

const meta = {
  title: 'Compositions/Home/QuickTemplateList',
  component: QuickTemplateList,
  args: { onTemplateClick: fn() },
  decorators: [
    (Story) => (
      <div className="bg-background-normal-normal flex justify-center p-10">
        <div className="w-190">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'home',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: `https://www.figma.com/design/${FIGMA_FILE_KEY}/%F0%9F%8D%85-Design-System?node-id=17496-46091&m=dev`,
        fileKey: FIGMA_FILE_KEY,
        nodeId: NODE_ID,
      },
      viewport: { width: 900, height: 260 },
      states: ['default', 'row-hover'],
      layoutNotes: [
        '2열로 흐르고 행 간격 12, 열 간격 24. 각 칸은 flex-1이라 컨테이너 폭을 나눠 갖는다.',
        '행 높이 40은 아이콘·라벨보다 커서 py가 아니라 h-10으로 고정한다.',
        '화살표는 hover에서만 렌더되어 그만큼 라벨 칸이 줄어든다 — 시안과 같은 동작이다.',
      ],
      dataNotes: ['questionTips의 tipData 순서를 그대로 노출한다 — 인덱스가 곧 템플릿 선택 값이다.'],
      reuseNotes: ['Reuses tipData from features/home/constants/questionTips.'],
      interactionNotes: ['Clicking a row reports its tipData index so the composer can insert that template.'],
      tokenNotes: [
        'Figma Text/Normal/Neutral maps to text-text-normal-neutral.',
        'Figma Icon/Normal/Neutral maps to text-icon-normal-neutral.',
        'Figma Fill/Normal/interaction/Hover maps to hover:bg-fill-normal-interaction-hover.',
        'Figma radius/lg maps to rounded-lg.',
      ],
    }),
  },
} satisfies Meta<typeof QuickTemplateList>;

export default meta;

type Story = StoryObj<typeof QuickTemplateList>;

export const Default: Story = {
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('시안 순서 그대로 6개가 뜬다', async () => {
      const rows = canvas.getAllByRole('button');
      await expect(rows).toHaveLength(6);
      await expect(rows.map((row) => row.textContent)).toEqual(tipData.map((tip) => tip.title));
    });

    await step('2열이고 같은 행의 두 칸은 폭이 같다', async () => {
      const rows = canvas.getAllByRole('button');
      const [first, second, third] = rows.map((row) => row.getBoundingClientRect());
      await expect(first.top).toBe(second.top);
      await expect(third.top).toBeGreaterThan(first.top);
      await expect(Math.round(second.width)).toBe(Math.round(first.width));
    });

    await step('행 높이 40, 열 간격 24, 행 간격 12', async () => {
      const rows = canvas.getAllByRole('button');
      const [first, second, third] = rows.map((row) => row.getBoundingClientRect());
      await expect(Math.round(first.height)).toBe(40);
      await expect(Math.round(second.left - first.right)).toBe(24);
      await expect(Math.round(third.top - first.bottom)).toBe(12);
    });

    await step('클릭하면 tipData 인덱스를 알린다', async () => {
      await userEvent.click(canvas.getByRole('button', { name: tipData[2].title }));
      await expect(args.onTemplateClick).toHaveBeenCalledWith(2);
    });
  },
};
