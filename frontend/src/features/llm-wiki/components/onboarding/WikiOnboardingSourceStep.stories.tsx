import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  BACKFILL_NOTICE_TEXT,
  CHANNEL_FIELD_CAPTION,
  CHANNEL_FIELD_LABEL,
  CHANNEL_PICKER_PLACEHOLDER,
  CHANNEL_TABLE_HEADERS,
  ONBOARDING_BACK_LABEL,
  ONBOARDING_CHANNEL_ROWS,
  ONBOARDING_FINISH_LABEL,
  ONBOARDING_SOURCE_HEADING,
  ONBOARDING_STEPS,
  SCHEDULE_FIELDS,
  SCHEDULE_RESULT_TEXT,
} from '../../fixtures/llmWikiOnboardingFixtures';
import WikiOnboardingSourceStep from './WikiOnboardingSourceStep';

const onNext = fn();
const onBack = fn();

const baseArgs = {
  steps: ONBOARDING_STEPS,
  heading: ONBOARDING_SOURCE_HEADING,
  channelLabel: CHANNEL_FIELD_LABEL,
  channelCaption: CHANNEL_FIELD_CAPTION,
  channelPickerPlaceholder: CHANNEL_PICKER_PLACEHOLDER,
  onOpenChannelPicker: fn(),
  channelTableHeaders: CHANNEL_TABLE_HEADERS,
  channelRows: ONBOARDING_CHANNEL_ROWS,
  scheduleFields: SCHEDULE_FIELDS,
  onOpenScheduleField: fn(),
  resultText: SCHEDULE_RESULT_TEXT,
  backfillNoticeText: BACKFILL_NOTICE_TEXT,
  backLabel: ONBOARDING_BACK_LABEL,
  onBack,
  nextLabel: ONBOARDING_FINISH_LABEL,
  onNext,
  onExit: fn(),
};

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/WikiOnboardingSourceStep',
  component: WikiOnboardingSourceStep,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18071-83322',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18071:83322',
      },
      viewport: { width: 1200 },
      states: ['default', 'channel-list-loading', 'channel-list-error'],
      dataNotes: [
        '**8/14 델타 반영**: 일정 필드가 2열+별도줄 → 3열 한 줄, 배너 아이콘 info_filled → megaphone, 날짜 표기 2025-01-23 → 2025.01.23.',
        '**하단 액션 바가 신설됐다** — 8/13 감사에서 MISSING이던 진행 CTA가 FOUND가 됐다. 이전 스토리의 "CTA 부재" 어서션은 폐기하고 존재 어서션으로 뒤집었다.',
        '드롭다운은 닫힌 트리거만 그린다 — 열림 메뉴·옵션 집합은 여전히 시안에 없다(감사 UNKNOWN). 표시값 "1분"과 완료 화면 요약 "매일"·"자정"이 어긋난 채 남아 있어 디자이너 질문 대상이다.',
        '채널 목록의 로딩·빈·에러는 8/14 시안에도 없다 — 8/13 사용자 승인 구현분을 유지한다.',
      ],
      layoutNotes: ['일정 3열 grid-cols-3 gap-4 — 시안 필드 폭 325.33은 (1008−32)/3의 결과값이라 고정하지 않는다.'],
    }),
  },
} satisfies Meta<typeof WikiOnboardingSourceStep>;

export default meta;
type Story = StoryObj<typeof WikiOnboardingSourceStep>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { level: 1, name: ONBOARDING_SOURCE_HEADING })).toBeInTheDocument();
    await expect(canvas.getByText(CHANNEL_FIELD_CAPTION)).toBeInTheDocument();
    await expect(canvas.getByText(SCHEDULE_RESULT_TEXT)).toBeInTheDocument();
    await expect(canvas.getByText(BACKFILL_NOTICE_TEXT)).toBeInTheDocument();
    await expect(canvas.getAllByRole('row')).toHaveLength(6);

    // 일정 3필드가 한 행에 놓인다(8/14 변경분)
    const triggers = SCHEDULE_FIELDS.map((field) => canvas.getByText(field.label).closest('div')!);
    const tops = triggers.map((el) => el.getBoundingClientRect().top);
    await expect(new Set(tops).size).toBe(1);

    // 하단 액션 바 2개 — 8/13 MISSING이 FOUND로 뒤집힌 지점
    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_BACK_LABEL }));
    await expect(onBack).toHaveBeenCalled();
    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));
    await expect(onNext).toHaveBeenCalled();
  },
};

/** 채널 목록만 로딩이고 나머지 폼은 그대로 — 로딩이 화면 전체를 덮지 않는다 */
export const ChannelListLoading: Story = {
  args: { ...baseArgs, channelRows: [], channelListStatus: 'loading' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('status', { name: '채널 목록 불러오는 중' })).toBeInTheDocument();
    await expect(canvas.getByText(SCHEDULE_RESULT_TEXT)).toBeInTheDocument();
  },
};

export const ChannelListError: Story = {
  args: { ...baseArgs, channelRows: [], channelListStatus: 'error', onRetryChannelList: fn() },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('alert')).toHaveTextContent('채널 목록을 불러오지 못했습니다');

    await userEvent.click(canvas.getByRole('button', { name: '다시 시도' }));
    await expect(args.onRetryChannelList).toHaveBeenCalled();
  },
};
