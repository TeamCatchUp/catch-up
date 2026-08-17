import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { filterSlashItems, SLASH_ITEMS } from './slashItems';
import SlashMenu from './SlashMenu';

/** Figma 시안이 없어 designSource는 'dev-preview'다. 에디터 없이 단독으로 열린다. */
const meta = {
  title: 'Compositions/LLM Wiki/Editor/SlashMenu',
  component: SlashMenu,
  tags: ['autodocs'],
  args: { items: SLASH_ITEMS, onSelect: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      viewport: { width: 320, height: 420 },
      states: ['default', 'filtered', 'no-results'],
      reuseNotes: [
        'cmdk 직접 import 금지 — @/shared/components/ui/command 래퍼를 쓴다(eslint.config 72행).',
        'CommandItem의 data-[selected=true]:bg-fill-normal-interaction-hover 토큰을 그대로 받는다.',
      ],
      dataNotes: [
        '항목은 props다 — 컴포넌트는 블록 종류를 알지 못한다.',
        '아이콘이 있는 항목은 글머리 목록·구분선 둘뿐이다. 제목·코드·인용은 자산이 리포에 없어 라벨만 렌더된다.',
      ],
      interactionNotes: [
        'shouldFilter={false}다. 필터는 filterSlashItems()가 하고 결과만 items로 받는다.',
        '포커스는 에디터에 있다 — 키보드는 밖에서 onKeyDown 핸들로 넣는다. 이 스토리는 마우스 선택만 검증한다.',
      ],
    }),
  },
} satisfies Meta<typeof SlashMenu>;

export default meta;
type Story = StoryObj<typeof SlashMenu>;

/** 전체 항목 11종. */
export const Default: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('제목 1')).toBeInTheDocument();
    await expect(canvas.getByText('글머리 목록')).toBeInTheDocument();
    await expect(canvas.getByText('구분선')).toBeInTheDocument();
    // 2차 블록 3종
    await expect(canvas.getByText('체크박스')).toBeInTheDocument();
    await expect(canvas.getByText('표')).toBeInTheDocument();
    await expect(canvas.getByText('콜아웃')).toBeInTheDocument();

    // 범위 밖 항목(이미지·멘션·문서 링크)이 새어들어오면 안 된다.
    await expect(canvas.queryByText('이미지')).toBeNull();

    await userEvent.click(canvas.getByText('인용'));
    await expect(args.onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'blockquote' }));
  },
};

/** 한글 쿼리 필터. cmdk가 아니라 filterSlashItems()가 거른 결과를 받는다. */
export const Filtered: Story = {
  args: { items: filterSlashItems(SLASH_ITEMS, '제') },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('제목 1')).toBeInTheDocument();
    await expect(canvas.getByText('제목 2')).toBeInTheDocument();
    await expect(canvas.queryByText('인용')).toBeNull();
  },
};

/** 맞는 항목이 없을 때. 목록이 통째로 되돌아오면 안 된다. */
export const NoResults: Story = {
  args: { items: [] },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('일치하는 블록이 없습니다')).toBeInTheDocument();
    await expect(canvas.queryByText('제목 1')).toBeNull();
  },
};
