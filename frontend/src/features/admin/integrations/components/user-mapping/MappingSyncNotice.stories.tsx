import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import MappingSyncNotice from './MappingSyncNotice';

const meta = {
  title: 'Compositions/Admin/Integrations/User Mapping/MappingSyncNotice',
  component: MappingSyncNotice,
  tags: ['autodocs'],
  args: { variant: 'partial-failure', lastSyncedAt: '2026. 2. 9. 01:31', onRetry: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17379-92020',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17379:92020',
      },
      viewport: { width: 1100, height: 120 },
      states: ['partial-failure', 'csv-required'],
      dataNotes: [
        '구버전 승계 — 사용자 승인 2026-08-04 (감사 §4).',
        'px 16 py 10, gap 16, radius 8, accent-red-lighten 배경, 문구 15px accent-red-default.',
        '마지막 동기화 시각의 API 필드는 배선 때 확정 — 여기선 문자열 prop.',
      ],
    }),
  },
} satisfies Meta<typeof MappingSyncNotice>;

export default meta;

type Story = StoryObj<typeof MappingSyncNotice>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-250 p-4">{children}</div>
);

export const PartialFailure: Story = {
  render: (args) => (
    <Frame>
      <MappingSyncNotice {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('일부 유저 동기화에 실패했습니다.')).toBeInTheDocument();
    await expect(canvas.getByText(/마지막 동기화/)).toBeInTheDocument();
    await expect(canvas.getByText('2026. 2. 9. 01:31')).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: /동기화 재시도/ }));
    await expect(args.onRetry).toHaveBeenCalled();
  },
};

/** 매핑 데이터가 하나도 없을 때 — CSV 업로드 유도 */
export const CsvRequired: Story = {
  args: { variant: 'csv-required', lastSyncedAt: null, onRetry: undefined },
  render: (args) => (
    <Frame>
      <MappingSyncNotice {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('CSV 파일을 업로드해주세요!')).toBeInTheDocument();
    await expect(canvas.queryByRole('button')).not.toBeInTheDocument();
  },
};
