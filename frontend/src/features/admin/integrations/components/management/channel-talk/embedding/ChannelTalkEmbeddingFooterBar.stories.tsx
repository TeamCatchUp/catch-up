import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../../.storybook/catchupStoryParameters';
import ChannelTalkEmbeddingFooterBar from './ChannelTalkEmbeddingFooterBar';

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkEmbeddingFooterBar',
  component: ChannelTalkEmbeddingFooterBar,
  tags: ['autodocs'],
  args: {
    channelCount: 5,
    documentCount: 18,
    allSelected: false,
    onToggleAll: fn(),
    onEmbed: fn(),
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17414-97736',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17414:97736',
      },
      viewport: { width: 780, height: 120 },
      states: ['some', 'all', 'none', 'channel-only'],
      layoutNotes: ['780×60, 위선만 있고 배경 없음. px 32 / py 12, gap 6.'],
      dataNotes: [
        '스텝 ①의 ChannelTalkFooterBar(17345:84633)와 다른 물건이다 — 저건 버튼 2개.',
        '집계는 숫자만 #3385FF로 강조된다.',
      ],
      interactionNotes: [
        '체크 표시는 전부 선택했을 때만 — 일부 선택 indeterminate는 쓰지 않는다(사용자 결정 2026-08-04).',
        '라벨 텍스트가 버튼 안에 있어 텍스트 클릭도 토글이다.',
      ],
    }),
  },
} satisfies Meta<typeof ChannelTalkEmbeddingFooterBar>;

export default meta;

type Story = StoryObj<typeof ChannelTalkEmbeddingFooterBar>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195">{children}</div>
);

/** 일부 선택 — 체크는 비어 있다. indeterminate 표시를 쓰지 않는다 */
export const SomeSelected: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);
    const checkbox = canvas.getByRole('checkbox', { name: '전체 선택하기' });

    await expect(checkbox).toHaveAttribute('aria-checked', 'false');
    await expect(canvas.getByText('개 채널')).toBeInTheDocument();

    // 라벨 텍스트가 버튼 안에 있다 — 텍스트 클릭도 토글
    await userEvent.click(canvas.getByText('전체 선택하기'));
    await expect(args.onToggleAll).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: '임베딩하기' }));
    await expect(args.onEmbed).toHaveBeenCalled();
  },
};

export const AllSelected: Story = {
  args: { allSelected: true },
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('checkbox', { name: '전체 선택하기' })).toHaveAttribute('aria-checked', 'true');
  },
};

/** 하나도 안 고르면 임베딩할 대상이 없다 */
export const NoneSelected: Story = {
  args: { channelCount: 0, documentCount: 0, allSelected: false },
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('checkbox', { name: '전체 선택하기' })).toHaveAttribute('aria-checked', 'false');
    await expect(canvas.getByRole('button', { name: '임베딩하기' })).toBeDisabled();
  },
};

/** 채널 대화만 선택 — 도큐먼트 스페이스가 없어도 제출 가능해야 한다 (develop 동작 승계) */
export const ChannelOnly: Story = {
  args: { channelCount: 1, documentCount: 0, allSelected: false },
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);
    const submit = canvas.getByRole('button', { name: '임베딩하기' });

    await expect(submit).toBeEnabled();
    await userEvent.click(submit);
    await expect(args.onEmbed).toHaveBeenCalled();
  },
};
