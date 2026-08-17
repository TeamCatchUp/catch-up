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
  onSelectScheduleOption: fn(),
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
        '**기본값·주기 선택지는 기획 문서(Confluence 160301060 §3.2)가 원천이다.** 시안 트리거의 "1분"은 공용 컴포넌트 필러였고 완료 화면 요약("매일"·"자정")이 기획과 일치한다 — 값 불일치가 이렇게 해소됐다.',
        '주기만 드롭다운이 열린다(6시간마다/12시간마다/매일/주 1회). 백필은 선택지 라벨이 기획에 확정돼 있지 않고(“최근 N개월”의 N 미정), 실행 시각은 기획이 “시각 선택, 기본 자정”까지만 정해 둘 다 트리거만 그린다.',
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

    // 기본값이 기획대로다 — 시안 필러 "1분"이 아니다
    await expect(canvas.getByText('매일')).toBeInTheDocument();
    await expect(canvas.getByText('자정')).toBeInTheDocument();

    // 하단 액션 바 2개 — 8/13 MISSING이 FOUND로 뒤집힌 지점
    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_BACK_LABEL }));
    await expect(onBack).toHaveBeenCalled();
    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));
    await expect(onNext).toHaveBeenCalled();
  },
};

/** 채널 피커에서 고르면 아래 표에 등록된다 — 8/14에 확정된 입력창↔표 관계 */
export const ChannelPickerAddsRow: Story = {
  args: {
    ...baseArgs,
    channelRows: [],
    availableChannels: ONBOARDING_CHANNEL_ROWS,
    onSelectChannel: fn(),
  },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);

    // 아직 고른 채널이 없으니 표 자리에는 안내만 있다
    await expect(canvas.getByText('아직 선택한 채널이 없습니다')).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: new RegExp(CHANNEL_PICKER_PLACEHOLDER) }));

    // 메뉴는 포털로 body에 붙는다
    const menu = await within(document.body).findByRole('menu');
    const items = within(menu).getAllByRole('menuitem');
    await expect(items).toHaveLength(ONBOARDING_CHANNEL_ROWS.length);

    await userEvent.click(items[0]);
    await expect(args.onSelectChannel).toHaveBeenCalledWith(ONBOARDING_CHANNEL_ROWS[0].channel.id);
  },
};

/** 이미 고른 채널은 다시 고를 수 없다 — 표에 중복으로 쌓이지 않게 하는 안전장치 */
export const ChannelPickerHidesPicked: Story = {
  args: {
    ...baseArgs,
    channelRows: [ONBOARDING_CHANNEL_ROWS[0]],
    availableChannels: ONBOARDING_CHANNEL_ROWS,
    onSelectChannel: fn(),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: new RegExp(CHANNEL_PICKER_PLACEHOLDER) }));

    const menu = await within(document.body).findByRole('menu');
    await expect(within(menu).getAllByRole('menuitem')).toHaveLength(ONBOARDING_CHANNEL_ROWS.length - 1);
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
