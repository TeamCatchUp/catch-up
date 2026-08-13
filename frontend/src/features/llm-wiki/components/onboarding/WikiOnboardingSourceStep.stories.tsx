import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  BACKFILL_NOTICE_TEXT,
  CHANNEL_FIELD_CAPTION,
  CHANNEL_FIELD_LABEL,
  CHANNEL_PICKER_PLACEHOLDER,
  CHANNEL_TABLE_HEADERS,
  ONBOARDING_CHANNEL_ROWS,
  ONBOARDING_SOURCE_HEADING,
  ONBOARDING_STEPS,
  SCHEDULE_FIELDS,
  SCHEDULE_RESULT_TEXT,
} from '../../fixtures/llmWikiOnboardingFixtures';
import WikiOnboardingSourceStep from './WikiOnboardingSourceStep';

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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18071-83320',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18071:83320',
      },
      viewport: { width: 1200 },
      states: ['default'],
      dataNotes: [
        '채널 라벨·수집 범위 캡션·백필 배너·결과 문장·"지금부터"는 시안 실카피. 채널 행·주기/실행 시간 표시값("1분")은 필러라 카피 미정(TBD) — 스토리명에 반영. 명세 기본값은 매일/자정이나 시안이 우선.',
        '드롭다운은 닫힌 트리거만 그린다 — 열림 메뉴·옵션 집합·백필 비활성 옵션은 시안에 없다(감사 UNKNOWN, 발명 금지).',
        '결과 문장의 값 조합별 변형 규칙은 미확정이라 문자열 props로만 받는다.',
      ],
      layoutNotes: [
        '주기·백필 2열 = grid-cols-2 gap-x-6(시안 열 간격 24). 트리거 높이 46 = h-11.5(ChannelTalk 드롭다운과 동일 규격), 채널 피커는 54 = h-13.5.',
        '카드 p-8, 구획 간 gap-8, 구획 내 gap-3 — 시안 오프셋(라벨→캡션→인풋→표 12px 간격, 구획 간 32px)에서 유도.',
      ],
      interactionNotes: [
        '하단 진행 CTA는 시안 부재(감사 MISSING) — 렌더하지 않으며 play가 부재를 어서션으로 고정한다. 디자이너가 그리면 이 어서션부터 풀 것.',
      ],
    }),
  },
} satisfies Meta<typeof WikiOnboardingSourceStep>;

export default meta;
type Story = StoryObj<typeof WikiOnboardingSourceStep>;

export const DefaultCopyTBD: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { level: 1, name: ONBOARDING_SOURCE_HEADING })).toBeInTheDocument();
    await expect(canvas.getByText(CHANNEL_FIELD_CAPTION)).toBeInTheDocument();
    await expect(canvas.getByText(CHANNEL_PICKER_PLACEHOLDER)).toBeInTheDocument();

    // 일정 필드 3종의 닫힌 트리거 + 결과 문장 + 백필 배너
    await expect(canvas.getByText('얼마나 자주 갱신할까요?')).toBeInTheDocument();
    await expect(canvas.getByText('지금부터')).toBeInTheDocument();
    await expect(canvas.getByText(SCHEDULE_RESULT_TEXT)).toBeInTheDocument();
    await expect(canvas.getByText(BACKFILL_NOTICE_TEXT)).toBeInTheDocument();

    // 채널 표가 5행으로 그려진다 (헤더 1 + 데이터 5)
    await expect(canvas.getAllByRole('row')).toHaveLength(6);

    // 진행 CTA 부재 고정 — 시안 MISSING이라 발명하지 않았다는 회귀 방지 어서션
    await expect(canvas.queryByRole('button', { name: '다음단계' })).not.toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '완료' })).not.toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '위키 만들기' })).not.toBeInTheDocument();
  },
};
