import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fireEvent, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  ONBOARDING_BACK_LABEL,
  ONBOARDING_COMPLETE_HEADING,
  ONBOARDING_FINISH_LABEL,
  ONBOARDING_NEXT_STEPS_TITLE,
  ONBOARDING_STEPS,
  ONBOARDING_SUMMARY_CHANNEL_LABEL,
  ONBOARDING_SUMMARY_SECTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import type { OnboardingSummaryRow } from '../../types/llmWikiOnboarding';
import { buildOnboardingNextSteps } from '../../utils/onboarding/onboardingNextSteps';
import { buildExecutionAnchor, intervalMinutesOf, resolveNextRunAt } from '../../utils/onboarding/scheduleAnchor';
import OnboardingChannelTable from './OnboardingChannelTable';
import type { SummarySectionView } from './OnboardingSummaryCard';
import WikiOnboardingCompleteStep from './WikiOnboardingCompleteStep';

const onFinish = fn();
const onBack = fn();

// 스토리를 시각에 종속시키지 않으려고 2026-08-19(수) 13:00 로컬을 고정한다
const NOW = new Date(2026, 7, 19, 13, 0, 0);

const CHANNEL_ROWS = [
  { channel: { credentialId: 1, name: '고객지원', externalId: 'ct-1', isConfigured: true } },
  { channel: { credentialId: 2, name: '기술문의', externalId: 'ct-2', isConfigured: true } },
];

const nextRunAt = (pollingOptionId: string, runTimeOptionId: string) =>
  resolveNextRunAt(buildExecutionAnchor(runTimeOptionId, NOW), intervalMinutesOf(pollingOptionId), NOW);

/** 완료 화면은 라우트가 채운 값만 그린다 — 여기서는 그 결과를 흉내 낸다 */
function summarySections(collectionValues: Record<string, string>): readonly SummarySectionView[] {
  const [purposeSection, collectionSection] = ONBOARDING_SUMMARY_SECTIONS;
  const fill = (row: OnboardingSummaryRow) => ({
    ...row,
    values: collectionValues[row.label] ? [collectionValues[row.label]] : row.values,
  });

  return [
    purposeSection,
    {
      ...collectionSection,
      rows: collectionSection.rows.map(fill),
      lead: {
        label: ONBOARDING_SUMMARY_CHANNEL_LABEL,
        content: <OnboardingChannelTable headers={{ name: '채널명' }} rows={CHANNEL_ROWS} />,
      },
    },
  ];
}

const baseArgs = {
  steps: ONBOARDING_STEPS,
  heading: ONBOARDING_COMPLETE_HEADING,
  summarySections: summarySections({ '갱신 주기': '매일', 언제부터: '지금부터', 실행시간: '자정' }),
  nextStepsTitle: ONBOARDING_NEXT_STEPS_TITLE,
  nextSteps: buildOnboardingNextSteps({
    backfillOptionId: 'from-now',
    nextRunAt: nextRunAt('daily', 'midnight'),
    now: NOW,
  }),
  backLabel: ONBOARDING_BACK_LABEL,
  onBack,
  finishLabel: ONBOARDING_FINISH_LABEL,
  onFinish,
  onExit: fn(),
};

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/WikiOnboardingCompleteStep',
  component: WikiOnboardingCompleteStep,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18318-51554',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18318:51554',
      },
      viewport: { width: 1200 },
      states: ['default', 'schedule-variant', 'submitting'],
      dataNotes: [
        '**8/14 신규 FOUND.** 8/13 감사의 "완료 화면은 시안에 없다 → 만들지 않는다" 판정이 뒤집힌 결과물이다.',
        '"위키를 만들면" 3줄이 명세의 완료 화면 3요소와 정확히 대응한다 — ①② 시간 약속, ③ 검수 안내(사람의 승인). **별도 철학 문단은 시안에 없어 만들지 않았다.**',
        '**①②는 이제 선택값에서 파생된다.** ②의 시각은 APScheduler interval 규칙(앵커=위상)으로 계산한 첫 실행 시각이라, 6시간마다·오전 6시를 고르면 "내일 자정"이 아니라 "오늘 오후 6시"가 된다. ③만 제품 원칙이라 고정.',
        '요약의 문서 종류 값은 1단계 프리셋 라벨의 축약형("기능 요청 정리"→"기능 요청")이다 — 시안 그대로 뒀다.',
        '**백필 선택별 분기 문구는 시안에 한 벌뿐이다**(감사 §5). 문면은 유지하되 선택값에서 파생되게 두어 백필이 열리면 따라간다.',
      ],
      layoutNotes: [
        '요약 행은 라벨 80 고정(w-20) + 값 영역. 문서 종류·채널처럼 값이 여러 개인 행이 있어 값을 flex-wrap으로 나란히 놓는다.',
        '하단 액션 바는 3단계 공용 OnboardingActionBar — 콘텐츠 패딩 밖 형제라 상단 테두리가 전폭을 긋는다.',
      ],
      tokenNotes: [
        '"위키를 만들면" 카드 = bg-fill-primary-normal-assistive(#F7FBFF) + 제목·항목 text-text-primary-normal(#005EEB) + 체크 icon-primary-assistive(#3385FF).',
      ],
      interactionNotes: [
        '"완료하기"는 채널 생성 1회 + 고른 채널마다 수집 설정 저장 N회를 부른다. 진행·성공·실패 시각은 시안에 없어 만들지 않았다 — 실패는 토스트로만 알린다.',
        '제출 중에는 버튼이 잠긴다(finishDisabled). 시각 발명이 아니라 같은 제출이 두 번 나가는 것을 막는 장치다.',
      ],
    }),
  },
} satisfies Meta<typeof WikiOnboardingCompleteStep>;

export default meta;
type Story = StoryObj<typeof WikiOnboardingCompleteStep>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { level: 1, name: ONBOARDING_COMPLETE_HEADING })).toBeInTheDocument();

    // 요약 2구역 + 행 8개(위키 목적 5 + 수집 설정 3 — 채널은 행이 아니라 표다)
    await expect(canvas.getByRole('heading', { level: 3, name: '위키 목적' })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 3, name: '수집 설정' })).toBeInTheDocument();
    await expect(canvas.getAllByRole('term')).toHaveLength(8);

    // 채널 표는 고른 채널을 그대로 싣고, 열은 채널명 하나뿐이다
    await expect(canvas.getByText(ONBOARDING_SUMMARY_CHANNEL_LABEL)).toBeInTheDocument();
    await expect(canvas.getAllByRole('columnheader')).toHaveLength(1);
    await expect(canvas.queryByText('최근 수정일')).not.toBeInTheDocument();
    await expect(canvas.getByText('고객지원')).toBeInTheDocument();

    // 문서 종류 값 3개는 배지로 놓인다 — 다른 행은 평문이라 배경이 없다
    const docKindValues = canvas.getByText('문서 종류').nextElementSibling!;
    await expect(docKindValues.children).toHaveLength(3);
    const [badge] = Array.from(docKindValues.children);
    const [plain] = Array.from(canvas.getByText('문체').nextElementSibling!.children);
    await expect(getComputedStyle(badge).backgroundColor).not.toBe(getComputedStyle(plain).backgroundColor);

    // 명세 3요소가 전부 있고, 넷째 줄을 발명하지 않았다
    // 스테퍼도 li를 쓰므로 목록을 이름으로 좁힌다
    const nextStepsList = canvas.getByRole('list', { name: ONBOARDING_NEXT_STEPS_TITLE });
    const nextSteps = within(nextStepsList).getAllByRole('listitem');
    await expect(nextSteps).toHaveLength(3);
    await expect(nextSteps[1]).toHaveTextContent('내일 자정 첫 갱신 때');
    await expect(nextSteps[2]).toHaveTextContent('문서는 사람의 승인 없이는 바뀌지 않아요');

    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));
    await expect(onFinish).toHaveBeenCalled();
  },
};

/** 6시간마다·오전 6시. 앵커가 위상이라 첫 실행이 고른 시각(오전 6시)이 아닌 다음 경계로 간다 */
export const SixHourlyFromMorning: Story = {
  args: {
    ...baseArgs,
    summarySections: summarySections({ '갱신 주기': '6시간마다', 언제부터: '지금부터', 실행시간: '오전 6시' }),
    nextSteps: buildOnboardingNextSteps({
      backfillOptionId: 'from-now',
      nextRunAt: nextRunAt('6h', '6am'),
      now: NOW,
    }),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // 수집 설정 요약이 2단계 선택을 그대로 비춘다
    await expect(canvas.getByText('갱신 주기').nextElementSibling).toHaveTextContent('6시간마다');
    await expect(canvas.getByText('실행시간').nextElementSibling).toHaveTextContent('오전 6시');

    const nextStepsList = canvas.getByRole('list', { name: ONBOARDING_NEXT_STEPS_TITLE });
    const nextSteps = within(nextStepsList).getAllByRole('listitem');
    await expect(nextSteps[1]).toHaveTextContent('오늘 오후 6시 첫 갱신 때');
    await expect(nextSteps[1]).not.toHaveTextContent('내일 자정');
  },
};

/** 제출 중 중복 클릭 방지. 새 시각을 만들지 않고 기존 disabled 상태만 쓴다 */
export const Submitting: Story = {
  args: { ...baseArgs, finishDisabled: true, onFinish: fn() },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    const finish = canvas.getByRole('button', { name: ONBOARDING_FINISH_LABEL });

    // 잠긴 버튼은 pointer-events가 없어 userEvent가 닿지 않는다 — 핸들러 차단만 확인한다
    await expect(finish).toBeDisabled();
    fireEvent.click(finish);
    await expect(args.onFinish).not.toHaveBeenCalled();
  },
};
