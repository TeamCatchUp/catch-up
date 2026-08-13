import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  DOC_KIND_FIELD_LABEL,
  DOC_KIND_SAMPLE_TITLE,
  FOLLOW_UP_EXAMPLE,
  FOLLOW_UP_MAX_LENGTH,
  FOLLOW_UP_PLACEHOLDER_TBD,
  ONBOARDING_NEXT_LABEL,
  ONBOARDING_PURPOSE_HEADING,
  ONBOARDING_STEPS,
  PURPOSE_FIELD_CAPTION,
  PURPOSE_FIELD_LABEL,
  TONE_CUSTOM_MAX_LENGTH,
  TONE_CUSTOM_OPTION,
  TONE_STYLE_FIELD_LABEL,
  WIKI_DOC_KIND_PRESETS,
  WIKI_NAME_FIELD,
  WIKI_PURPOSE_OPTIONS,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import WikiOnboardingPurposeStep from './WikiOnboardingPurposeStep';

const onNext = fn();

const baseArgs = {
  steps: ONBOARDING_STEPS,
  heading: ONBOARDING_PURPOSE_HEADING,
  basicInfoTitle: '기본 위키 정보',
  nameLabel: WIKI_NAME_FIELD.label,
  nameValue: '',
  onNameChange: fn(),
  namePlaceholder: WIKI_NAME_FIELD.placeholder,
  nameMaxLength: WIKI_NAME_FIELD.maxLength,
  purpose: {
    label: PURPOSE_FIELD_LABEL,
    caption: PURPOSE_FIELD_CAPTION,
    options: WIKI_PURPOSE_OPTIONS,
    selectedId: WIKI_PURPOSE_OPTIONS[0].id,
    onSelect: fn(),
    followUpValue: '',
    onFollowUpChange: fn(),
    followUpPlaceholder: FOLLOW_UP_PLACEHOLDER_TBD,
    followUpMaxLength: FOLLOW_UP_MAX_LENGTH,
    followUpExample: FOLLOW_UP_EXAMPLE,
  },
  formatTitle: '문서 형식',
  docKind: {
    label: DOC_KIND_FIELD_LABEL,
    presets: WIKI_DOC_KIND_PRESETS,
    selectedId: WIKI_DOC_KIND_PRESETS[0].id,
    onSelect: fn(),
    sampleTitle: DOC_KIND_SAMPLE_TITLE,
    sampleText: WIKI_DOC_KIND_PRESETS[0].sampleText,
  },
  tone: {
    label: TONE_STYLE_FIELD_LABEL,
    options: WIKI_TONE_STYLE_OPTIONS,
    selectedIds: [WIKI_TONE_STYLE_OPTIONS[0].id],
    onToggle: fn(),
    customLabel: TONE_CUSTOM_OPTION.label,
    customDescription: TONE_CUSTOM_OPTION.description,
    customValue: '',
    onCustomChange: fn(),
    customPlaceholder: FOLLOW_UP_PLACEHOLDER_TBD,
    customMaxLength: TONE_CUSTOM_MAX_LENGTH,
  },
  nextLabel: ONBOARDING_NEXT_LABEL,
  onNext,
};

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/WikiOnboardingPurposeStep',
  component: WikiOnboardingPurposeStep,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18007-46505',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18007:46505',
      },
      viewport: { width: 1200 },
      states: ['default'],
      dataNotes: [
        '시안 프레임은 다크 렌더(#1B1C1E 배경)지만 전 색을 시맨틱 토큰으로 매핑해 스토리는 라이트로 그린다 — 다크는 토큰이 따라온다(감사 §1 다크 컨텍스트 주의).',
        '이름 placeholder("CS 응답 위키, 제품 용어 사전")·헤딩·카드 제목은 시안 실카피. 입력 placeholder류 필러는 TBD 유지 — 스토리명에 반영.',
        '검증 실패·다음단계 비활성·이탈 확인은 그리지 않는다(감사 §7 금지 목록). 버튼은 시안대로 항상 활성.',
      ],
      layoutNotes: [
        '콘텐츠 px-16(시안 Margin 64), 스테퍼→헤딩→폼 세로 gap-8(시안 오프셋 66→98→173에서 유도), 카드 간 gap-5.',
        '이름 라벨 슬롯 w-[157px] — 시안 Textfield 시작 x에서 유도한 값이라 고정한다. 입력은 min-w-0 flex-1로 폭을 흡수(레벨당 흡수자 1개).',
        '하단 CTA 바는 full-bleed 형제 — 콘텐츠 패딩 밖에서 border-t가 전폭을 긋는다(py-2 + 버튼 36 = 시안 바 52).',
      ],
      tokenNotes: [
        '카드 bg-fill-normal-assistive + border-line-normal-neutral + rounded-2xl — 다크에서 #212225 카드가 같은 토큰으로 나온다.',
        '헤딩 text-display-xlarge(32/1.34/600), 카드 제목 text-heading-large(19), 필드 라벨 text-heading-small(15sb).',
      ],
      reuseNotes: ['CTA는 shared Button box-solid-primary md — 시안 Box Button(높이 36, 파랑 솔리드)과 규격 일치.'],
    }),
  },
} satisfies Meta<typeof WikiOnboardingPurposeStep>;

export default meta;
type Story = StoryObj<typeof WikiOnboardingPurposeStep>;

export const DefaultCopyTBD: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { level: 1, name: ONBOARDING_PURPOSE_HEADING })).toBeInTheDocument();
    await expect(canvas.getByText('기본 위키 정보')).toBeInTheDocument();
    await expect(canvas.getByText('문서 형식')).toBeInTheDocument();

    // 이름 카운터는 0/20에서 시작한다
    await expect(canvas.getByText('0/20')).toBeInTheDocument();

    // 1단계에는 하단 CTA가 시안에 실재한다 — 활성 상태로 클릭 가능
    const nextButton = canvas.getByRole('button', { name: ONBOARDING_NEXT_LABEL });
    await expect(nextButton).toBeEnabled();
    await userEvent.click(nextButton);
    await expect(onNext).toHaveBeenCalled();
  },
};
