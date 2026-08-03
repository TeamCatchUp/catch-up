import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import type { ChannelTalkChannel, ChannelTalkDocumentSpace } from '../../../types/channelTalkModel';
import ChannelTalkChannelCard from './ChannelTalkChannelCard';

const base: ChannelTalkChannel = {
  id: 'ch-1',
  name: '채널 1 text text text text text text text text text',
  accessKey: '',
  accessSecret: '',
  webhookToken: '',
  connectionStatus: 'idle',
  documentSpaces: [],
};

const filled: ChannelTalkChannel = {
  ...base,
  accessKey: 'abcdefg',
  accessSecret: 'abcdefg',
  webhookToken: 'abcdefg',
};

const documentSpace = (id: string, overrides: Partial<ChannelTalkDocumentSpace> = {}): ChannelTalkDocumentSpace => ({
  id,
  name: `도큐먼트 스페이스 ${id} texttexttexttexttexttexttexttexttext`,
  accessKey: 'abcdefg',
  accessSecret: 'abcdefg',
  syncInterval: '1hour',
  connectionStatus: 'idle',
  ...overrides,
});

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkChannelCard',
  component: ChannelTalkChannelCard,
  tags: ['autodocs'],
  args: {
    channel: base,
    onUpdate: fn(),
    onRemove: fn(),
    onAddDocumentSpace: fn(),
    onUpdateDocumentSpace: fn(),
    onRemoveDocumentSpace: fn(),
    onTestConnection: fn(),
    onTestDocumentSpaceConnection: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17363-100300',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17363:100300',
      },
      viewport: { width: 716, height: 500 },
      states: ['empty', 'filled', 'tested', 'error', 'with-document-spaces', 'document-space-tested'],
      interactionNotes: [
        '이 스토리는 레이아웃이 아니라 동작을 고정한다 — 카드 골격이 Figma 신규로 바뀌어도 통과해야 한다.',
        'tested면 폼이 접히고, 키가 다 차야 연결 테스트가 활성이며, 삭제는 확인 모달을 거친다.',
      ],
    }),
  },
} satisfies Meta<typeof ChannelTalkChannelCard>;

export default meta;

type Story = StoryObj<typeof ChannelTalkChannelCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

/** 키가 비면 연결 테스트를 못 누른다 */
export const Empty: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkChannelCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText(/채널 1/)).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /연결 테스트 하기/ })).toBeDisabled();
  },
};

/** 키 3종이 다 차면 연결 테스트가 열린다 */
export const Filled: Story = {
  args: { channel: filled },
  render: (args) => (
    <Frame>
      <ChannelTalkChannelCard {...args} />
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

/** 테스트 완료면 폼이 접힌다 — 바꾸려면 삭제 후 재등록 */
export const Tested: Story = {
  args: { channel: { ...filled, connectionStatus: 'tested' } },
  render: (args) => (
    <Frame>
      <ChannelTalkChannelCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('테스트 완료')).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: /연결 테스트 하기/ })).not.toBeInTheDocument();
    await expect(canvas.queryByText('Access Key')).not.toBeInTheDocument();
  },
};

/**
 * Figma "입력 전_Default_도큐먼트스페이스 추가 시" 변형.
 * 계층 표현(레일 세로선 · icon/reply · 들여쓰기)이 실제로 읽히는지 보는 유일한 스토리다.
 */
export const WithDocumentSpaces: Story = {
  args: {
    channel: { ...filled, documentSpaces: [documentSpace('1'), documentSpace('2', { accessKey: '', accessSecret: '' })] },
  },
  render: (args) => (
    <Frame>
      <ChannelTalkChannelCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText(/도큐먼트 스페이스 1/)).toBeInTheDocument();
    await expect(canvas.getByText(/도큐먼트 스페이스 2/)).toBeInTheDocument();

    // 채널 1 + 도큐먼트 2 = 연결 테스트 버튼 3개. 2번 도큐먼트만 키가 비어 비활성
    const testButtons = canvas.getAllByRole('button', { name: /연결 테스트 하기/ });
    await expect(testButtons).toHaveLength(3);
    await expect(testButtons[2]).toBeDisabled();

    await userEvent.click(canvas.getByRole('button', { name: /도큐먼트 스페이스$/ }));
    await expect(args.onAddDocumentSpace).toHaveBeenCalled();
  },
};

/** Figma "도큐먼트스페이스_테스트 완료" 변형 — 채널과 도큐먼트의 상태는 독립이다 */
export const DocumentSpaceTested: Story = {
  args: {
    channel: {
      ...filled,
      connectionStatus: 'tested',
      documentSpaces: [documentSpace('1', { connectionStatus: 'tested' }), documentSpace('2')],
    },
  },
  render: (args) => (
    <Frame>
      <ChannelTalkChannelCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 채널과 도큐먼트1이 접혀 "테스트 완료" 2개, 도큐먼트2만 폼이 열려 있다
    await expect(canvas.getAllByText('테스트 완료')).toHaveLength(2);
    await expect(canvas.getAllByRole('button', { name: /연결 테스트 하기/ })).toHaveLength(1);
  },
};

/** 오류면 메시지가 보이고 폼은 열린 채로 남는다 */
export const ErrorState: Story = {
  args: {
    channel: { ...filled, connectionStatus: 'error', errorMessage: '인증에 실패했습니다. 키를 확인해 주세요.' },
  },
  render: (args) => (
    <Frame>
      <ChannelTalkChannelCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('인증에 실패했습니다. 키를 확인해 주세요.')).toBeInTheDocument();
    await expect(canvas.getByText('Access Key')).toBeInTheDocument();
  },
};
