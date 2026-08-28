import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingRetryModal from './EmbeddingRetryModal';

const meta = {
  title: 'Compositions/Admin/Integrations/Modals/EmbeddingRetryModal',
  component: EmbeddingRetryModal,
  tags: ['autodocs'],
  args: {
    open: true,
    onOpenChange: fn(),
    onConfirm: fn(),
    totalCount: 128_400,
    successCount: 120_000,
    failedCount: 8_400,
    retryAttempt: 1,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      viewport: { width: 560, height: 640 },
      states: ['first-retry', 'exhausted', 'loading', 'no-retryable-records'],
      dataNotes: [
        '카피 분기 기준은 isFirstRetry = retryAttempt < 3 — 백엔드 sync_events.max_attempts 기본값(3)이며 attempt는 DB 제약상 그 이하다.',
        '로딩 중에는 onOpenChange가 undefined로 막혀 닫을 수 없다.',
        'confirmDisabled는 gap의 누락 레코드 0건일 때 — 빈 records 전송은 백엔드가 422로 거부한다.',
      ],
    }),
    docs: { story: { inline: false, height: '620px' } },
  },
} satisfies Meta<typeof EmbeddingRetryModal>;

export default meta;

type Story = StoryObj<typeof EmbeddingRetryModal>;

/** 한도 전(attempt < 3) — "실패한 N개만 다시 해볼까요?" 제안, 재시도 카운트 카드 없음 */
export const FirstRetry: Story = {
  play: async () => {
    const portal = within(document.body);
    await expect(portal.getByText('실패한 8,400개만 다시 해볼까요?')).toBeInTheDocument();
    // '임베딩 재시도'는 다이얼로그 타이틀에도 쓰이는 문구라 queryByText로는 부재를 단언할 수 없다
    // (복수 매치 시 testing-library가 예외를 던진다). 재시도 카운트 카드가 있으면 라벨이 중복되어
    // getAllByText 길이가 2가 되므로, 타이틀 1건만 남아있는지로 카드 부재를 확인한다.
    await expect(portal.getAllByText('임베딩 재시도')).toHaveLength(1);
  },
};

/** 한도 도달(attempt >= 3) — 재시도 카운트 카드 + "완료되지 못했어요" + 문의 유도 카피 */
export const Exhausted: Story = {
  args: { retryAttempt: 3, retryingCount: 3_200 },
  play: async () => {
    const portal = within(document.body);
    await expect(portal.getByText('8,400개가 완료되지 못했어요')).toBeInTheDocument();
    await expect(portal.getByText(/Catch Up에 문의해주세요/)).toBeInTheDocument();
    await expect(portal.getByText('3,200개')).toBeInTheDocument();
  },
};

/** 재시도 진행 중 — 블로킹 화면, 닫기 버튼 자체가 없다 */
export const Loading: Story = {
  args: { isLoading: true },
  play: async () => {
    const portal = within(document.body);
    await expect(portal.getByText(/다시 임베딩을 진행하고 있어요/)).toBeInTheDocument();
    await expect(portal.getByText('재시도가 완료되면 창이 바로 꺼집니다.')).toBeInTheDocument();
    await expect(portal.queryByRole('button')).not.toBeInTheDocument();
  },
};

/** 누락 레코드 0건 — 보낼 것이 없어 확인 버튼을 잠근다(빈 records는 백엔드 422) */
export const NoRetryableRecords: Story = {
  args: { failedCount: 0, confirmDisabled: true },
  play: async () => {
    const portal = within(document.body);
    await expect(portal.getByRole('button', { name: '다시 임베딩하기' })).toBeDisabled();
  },
};
