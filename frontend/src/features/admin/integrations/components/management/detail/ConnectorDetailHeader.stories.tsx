import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { Button } from '@/shared/components/ui/button';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorDetailHeader from './ConnectorDetailHeader';

const meta = {
  title: 'Compositions/Admin/Integrations/Detail/ConnectorDetailHeader',
  component: ConnectorDetailHeader,
  tags: ['autodocs'],
  args: {
    service: 'slack',
    title: 'Slack',
    description: '채팅 스레드에 묻힌 결정을 다시 꺼내오세요',
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=16922-134099',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '16922:134099',
      },
      viewport: { width: 780, height: 140 },
      states: ['before-connect', 'connected', 'long-title'],
      reuseNotes: ['연동 전과 연동됨이 같은 헤더를 쓴다 — 액션만 slot으로 바뀐다.'],
      layoutNotes: ['로고 칩 60 안에 로고 44, gap 16 (Figma 16939:65778).'],
    }),
  },
} satisfies Meta<typeof ConnectorDetailHeader>;

export default meta;

type Story = StoryObj<typeof ConnectorDetailHeader>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195 p-8">{children}</div>
);

/** 연동 전 — 매핑 확인하기 + 연결하기 */
export const BeforeConnect: Story = {
  args: {
    actions: (
      <>
        <Button variant="box-soft-primary" size="lg" onClick={fn()}>
          매핑 확인하기
        </Button>
        <Button variant="box-solid-primary" size="lg" onClick={fn()}>
          연결하기
        </Button>
      </>
    ),
  },
  render: (args) => (
    <Frame>
      <ConnectorDetailHeader {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('Slack')).toBeInTheDocument();
    await expect(canvas.getByText('채팅 스레드에 묻힌 결정을 다시 꺼내오세요')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '매핑 확인하기' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '연결하기' })).toBeInTheDocument();
  },
};

/** 연동됨 — 워크스페이스명이 제목이 되고 액션은 임베딩 추가 하나 */
export const Connected: Story = {
  args: {
    title: '캐치업-Catchup',
    description: 'Recover decisions buried in chat threads',
    actions: (
      <Button variant="box-solid-primary" size="lg" onClick={fn()}>
        임베딩 추가
      </Button>
    ),
  },
  render: (args) => (
    <Frame>
      <ConnectorDetailHeader {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('캐치업-Catchup')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '임베딩 추가' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '연결하기' })).not.toBeInTheDocument();
  },
};

export const LongTitle: Story = {
  args: {
    service: 'confluence',
    title: '아주 긴 워크스페이스 이름이 들어가는 경우의 말줄임 확인용 텍스트',
    description: '위키·기획 문서에서 근거와 함께 답 찾기',
    actions: (
      <Button variant="box-solid-primary" size="lg" onClick={fn()}>
        연결하기
      </Button>
    ),
  },
  render: (args) => (
    <Frame>
      <ConnectorDetailHeader {...args} />
    </Frame>
  ),
};
