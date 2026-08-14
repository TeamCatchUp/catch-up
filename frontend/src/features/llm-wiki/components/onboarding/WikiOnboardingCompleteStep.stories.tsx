import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  ONBOARDING_BACK_LABEL,
  ONBOARDING_COMPLETE_HEADING,
  ONBOARDING_FINISH_LABEL,
  ONBOARDING_NEXT_STEPS,
  ONBOARDING_NEXT_STEPS_TITLE,
  ONBOARDING_STEPS,
  ONBOARDING_SUMMARY_SECTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import WikiOnboardingCompleteStep from './WikiOnboardingCompleteStep';

const onFinish = fn();
const onBack = fn();

const baseArgs = {
  steps: ONBOARDING_STEPS,
  heading: ONBOARDING_COMPLETE_HEADING,
  summarySections: ONBOARDING_SUMMARY_SECTIONS,
  nextStepsTitle: ONBOARDING_NEXT_STEPS_TITLE,
  nextSteps: ONBOARDING_NEXT_STEPS,
  backLabel: ONBOARDING_BACK_LABEL,
  onBack,
  finishLabel: ONBOARDING_FINISH_LABEL,
  onFinish,
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
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18318-51554',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18318:51554',
      },
      viewport: { width: 1200 },
      states: ['default'],
      dataNotes: [
        '**8/14 신규 FOUND.** 8/13 감사의 "완료 화면은 시안에 없다 → 만들지 않는다" 판정이 뒤집힌 결과물이다.',
        '"위키를 만들면" 3줄이 명세의 완료 화면 3요소와 정확히 대응한다 — ①② 시간 약속, ③ 검수 안내(사람의 승인). **별도 철학 문단은 시안에 없어 만들지 않았다.**',
        '요약의 문서 종류 값은 1단계 프리셋 라벨의 축약형("기능 요청 정리"→"기능 요청")이다 — 시안 그대로 뒀다.',
        '**백필 선택별 분기 문구는 만들지 않았다** — 명세에는 있으나 시안은 "오늘 들어오는 상담부터" 한 벌뿐이다(감사 §5).',
      ],
      layoutNotes: [
        '요약 행은 라벨 80 고정(w-20) + 값 영역. 문서 종류·채널처럼 값이 여러 개인 행이 있어 값을 flex-wrap으로 나란히 놓는다.',
        '하단 액션 바는 3단계 공용 OnboardingActionBar — 콘텐츠 패딩 밖 형제라 상단 테두리가 전폭을 긋는다.',
      ],
      tokenNotes: [
        '"위키를 만들면" 카드 = bg-fill-primary-normal-assistive(#F7FBFF) + 제목·항목 text-text-primary-normal(#005EEB) + 체크 icon-primary-assistive(#3385FF).',
      ],
      interactionNotes: [
        '"완료하기"는 콜백만 부른다 — 제출 진행·성공·실패 상태가 시안에 없고 위키 생성 API도 없다(감사 §8).',
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

    // 요약 2구역 + 행 9개(위키 목적 5 + 수집 설정 4)
    await expect(canvas.getByRole('heading', { level: 3, name: '위키 목적' })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 3, name: '수집 설정' })).toBeInTheDocument();
    await expect(canvas.getAllByRole('term')).toHaveLength(9);

    // 문서 종류 행은 값 3개가 한 줄에 나란히 놓인다
    const docKindValues = canvas.getByText('문서 종류').nextElementSibling!;
    await expect(docKindValues.children).toHaveLength(3);

    // 명세 3요소가 전부 있고, 넷째 줄을 발명하지 않았다
    // 스테퍼도 li를 쓰므로 목록을 이름으로 좁힌다
    const nextStepsList = canvas.getByRole('list', { name: ONBOARDING_NEXT_STEPS_TITLE });
    const nextSteps = within(nextStepsList).getAllByRole('listitem');
    await expect(nextSteps).toHaveLength(3);
    await expect(nextSteps[2]).toHaveTextContent('문서는 사람의 승인 없이는 바뀌지 않아요');

    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_FINISH_LABEL }));
    await expect(onFinish).toHaveBeenCalled();
  },
};
