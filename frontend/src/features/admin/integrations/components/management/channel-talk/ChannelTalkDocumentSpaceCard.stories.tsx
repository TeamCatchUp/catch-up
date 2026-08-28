import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import type { ChannelTalkDocumentSpace } from '../../../types/channelTalkModel';
import ChannelTalkDocumentSpaceCard from './ChannelTalkDocumentSpaceCard';

const base: ChannelTalkDocumentSpace = {
  id: 'ds-1',
  name: '도큐먼트 스페이스 1 texttexttexttexttexttexttexttexttexttext',
  accessKey: '',
  accessSecret: '',
  syncInterval: '1hour',
  connectionStatus: 'idle',
};

const filled: ChannelTalkDocumentSpace = { ...base, accessKey: 'abcdefg', accessSecret: 'abcdefg' };

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkDocumentSpaceCard',
  component: ChannelTalkDocumentSpaceCard,
  tags: ['autodocs'],
  args: { documentSpace: base, onUpdate: fn(), onRemove: fn(), onTestConnection: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17367-102489',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17367:102489',
      },
      viewport: { width: 668, height: 420 },
      states: ['empty', 'filled', 'tested', 'error'],
      layoutNotes: ['icon/reply + 책 칩으로 채널 하위임을 표시한다. 채널 카드와 달리 동기화 주기 필드가 있다.'],
      interactionNotes: ['레이아웃이 아니라 동작을 고정한다 — 키 2종이 다 차야 연결 테스트가 활성이다.'],
    }),
  },
} satisfies Meta<typeof ChannelTalkDocumentSpaceCard>;

export default meta;

type Story = StoryObj<typeof ChannelTalkDocumentSpaceCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-167 p-6">{children}</div>
);

export const Empty: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkDocumentSpaceCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText(/도큐먼트 스페이스 1/)).toBeInTheDocument();
    // 라벨 span 과 그 부모 div 의 textContent 가 같아 둘 다 잡힌다
    await expect(canvas.getAllByText('동기화 주기 설정').length).toBeGreaterThan(0);
    await expect(canvas.getByRole('button', { name: /연결 테스트 하기/ })).toBeDisabled();
  },
};

export const Filled: Story = {
  args: { documentSpace: filled },
  render: (args) => (
    <Frame>
      <ChannelTalkDocumentSpaceCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    const testButton = canvas.getByRole('button', { name: /연결 테스트 하기/ });
    await expect(testButton).toBeEnabled();

    await userEvent.click(testButton);
    await expect(args.onTestConnection).toHaveBeenCalled();
  },
};

/** Figma "도큐먼트스페이스_테스트 완료" 변형 — 폼이 접힌다 */
export const Tested: Story = {
  args: { documentSpace: { ...filled, connectionStatus: 'tested' } },
  render: (args) => (
    <Frame>
      <ChannelTalkDocumentSpaceCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('테스트 완료')).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: /연결 테스트 하기/ })).not.toBeInTheDocument();
    await expect(canvas.queryAllByText('동기화 주기 설정')).toHaveLength(0);
  },
};

export const ErrorState: Story = {
  args: {
    documentSpace: { ...filled, connectionStatus: 'error', errorMessage: '인증에 실패했습니다. 키를 확인해 주세요.' },
  },
  render: (args) => (
    <Frame>
      <ChannelTalkDocumentSpaceCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('인증에 실패했습니다. 키를 확인해 주세요.')).toBeInTheDocument();
    await expect(canvas.getAllByText('동기화 주기 설정').length).toBeGreaterThan(0);
  },
};
