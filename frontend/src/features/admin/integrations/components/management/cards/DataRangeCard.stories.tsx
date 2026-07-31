import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import DataRangeCard from './DataRangeCard';

const SAMPLE_RANGE = '2026. 1. 1. ~ 2026. 7. 30.';

const meta = {
  title: 'Compositions/Admin/Integrations/DataRangeCard',
  component: DataRangeCard,
  tags: ['autodocs'],
  args: {
    connected: true,
    dataRange: SAMPLE_RANGE,
    alignStartWhenDisconnected: false,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['connected', 'disconnected', 'disconnected-align-start', 'long-text'],
      layoutNotes: [
        'VariantMatrix는 두 벌 사이의 drift 1건(미연결 시 정렬 규칙)을 나란히 보여준다.',
        '일반 도구는 항상 중앙, 채널톡은 미연결 시 좌측 — 이번 작업은 통일하지 않고 재현만 한다.',
      ],
    }),
  },
} satisfies Meta<typeof DataRangeCard>;

export default meta;

type Story = StoryObj<typeof DataRangeCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal flex w-160 flex-col p-6">{children}</div>
);

export const Playground: Story = {
  render: (args) => (
    <Frame>
      <DataRangeCard {...args} />
    </Frame>
  ),
};

export const Disconnected: Story = {
  args: { connected: false },
  render: (args) => (
    <Frame>
      <DataRangeCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연동되지 않았습니다.')).toBeInTheDocument();
    await expect(canvas.queryByText(SAMPLE_RANGE)).not.toBeInTheDocument();
  },
};

export const LongText: Story = {
  args: {
    dataRange: '2020. 12. 31. ~ 2026. 7. 30. (아주 긴 범위 문자열이 들어와도 잘림 처리가 되는지 확인)',
  },
  render: (args) => (
    <Frame>
      <DataRangeCard {...args} />
    </Frame>
  ),
};

/** 미연결 시 정렬 규칙 차이 — 위: 일반 도구(중앙) / 아래: 채널톡(좌측) */
export const VariantMatrix: Story = {
  render: () => (
    <Frame>
      <div className="flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <span className="text-label-xsmall text-text-normal-alternative">일반 도구 — 미연결 (중앙 정렬)</span>
          <DataRangeCard connected={false} dataRange={SAMPLE_RANGE} alignStartWhenDisconnected={false} />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-label-xsmall text-text-normal-alternative">채널톡 — 미연결 (좌측 정렬)</span>
          <DataRangeCard connected={false} dataRange={SAMPLE_RANGE} alignStartWhenDisconnected />
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-label-xsmall text-text-normal-alternative">연결됨 (두 벌 동일 — 중앙)</span>
          <DataRangeCard connected dataRange={SAMPLE_RANGE} alignStartWhenDisconnected />
        </div>
      </div>
    </Frame>
  ),
};
