import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  DOC_KIND_FIELD_LABEL,
  DOC_KIND_SAMPLE_CAPTION,
  DOC_KIND_SAMPLE_TITLE,
  INFO_CATEGORY_FIELD_LABEL,
  ONBOARDING_BASIC_INFO_TITLE,
  ONBOARDING_DOC_SETTING_TITLE,
  ONBOARDING_NEXT_LABEL,
  ONBOARDING_PURPOSE_HEADING,
  ONBOARDING_STEPS,
  PURPOSE_FIELD_LABEL,
  TEMPLATE_SAMPLE_TEXT_TBD,
  TONE_SAMPLE_TAG_LABEL,
  TONE_STYLE_FIELD_LABEL,
  WIKI_DOC_KIND_PRESETS,
  WIKI_INFO_CATEGORIES,
  WIKI_NAME_FIELD,
  WIKI_PURPOSE_OPTIONS,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import WikiOnboardingPurposeStep from './WikiOnboardingPurposeStep';

const onNext = fn();

const baseArgs = {
  steps: ONBOARDING_STEPS,
  heading: ONBOARDING_PURPOSE_HEADING,
  basicInfoTitle: ONBOARDING_BASIC_INFO_TITLE,
  nameLabel: WIKI_NAME_FIELD.label,
  nameValue: '',
  onNameChange: fn(),
  namePlaceholder: WIKI_NAME_FIELD.placeholder,
  nameMaxLength: WIKI_NAME_FIELD.maxLength,
  purpose: {
    categoryLabel: INFO_CATEGORY_FIELD_LABEL,
    categories: WIKI_INFO_CATEGORIES,
    selectedCategoryId: WIKI_INFO_CATEGORIES[0].id,
    onSelectCategory: fn(),
    purposeLabel: PURPOSE_FIELD_LABEL,
    purposeOptions: WIKI_PURPOSE_OPTIONS,
    selectedPurposeId: WIKI_PURPOSE_OPTIONS[0].id,
    onSelectPurpose: fn(),
  },
  docSettingTitle: ONBOARDING_DOC_SETTING_TITLE,
  docKind: {
    label: DOC_KIND_FIELD_LABEL,
    presets: WIKI_DOC_KIND_PRESETS,
    selectedId: WIKI_DOC_KIND_PRESETS[0].id,
    onSelect: fn(),
    sampleTitle: DOC_KIND_SAMPLE_TITLE,
    sampleCaption: DOC_KIND_SAMPLE_CAPTION,
    sampleText: TEMPLATE_SAMPLE_TEXT_TBD,
  },
  tone: {
    label: TONE_STYLE_FIELD_LABEL,
    options: WIKI_TONE_STYLE_OPTIONS,
    selectedId: WIKI_TONE_STYLE_OPTIONS[0].id,
    onSelect: fn(),
    sampleTagLabel: TONE_SAMPLE_TAG_LABEL,
  },
  nextLabel: ONBOARDING_NEXT_LABEL,
  onNext,
  onExit: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18007-46535',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18007:46535',
      },
      viewport: { width: 1200 },
      states: ['default'],
      dataNotes: [
        '**8/14 시안 갱신 반영.** 헤딩("이 위키는…"), 카드2 제목("문서 형식"→"문서 설정"), CTA("다음단계"→"다음 단계로"), 스텝3 라벨("완료"→"확인 및 완료")이 모두 바뀌었다.',
        '렌더 컨텍스트가 뒤바뀌어 이제 1단계가 라이트다(8/13에는 다크). 구현은 전부 시맨틱 토큰이라 영향 없다.',
        '검증 실패·버튼 비활성은 여전히 시안에 없어 만들지 않는다(감사 §8).',
        '이름 상한 20자는 백엔드 계약(POST /wiki/channels/onboarding, name 1~20)이다 — 초과분은 입력에서 잘리고 별도 에러 UI는 두지 않았다(시안 없음).',
      ],
      layoutNotes: [
        '이름 라벨 슬롯 w-[157px] — 시안 Textfield 시작 x에서 유도한 값이라 고정한다.',
        '하단 CTA는 공용 OnboardingActionBar(1단계는 다음 버튼만).',
      ],
    }),
  },
} satisfies Meta<typeof WikiOnboardingPurposeStep>;

export default meta;
type Story = StoryObj<typeof WikiOnboardingPurposeStep>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('heading', { level: 1, name: ONBOARDING_PURPOSE_HEADING })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 2, name: ONBOARDING_BASIC_INFO_TITLE })).toBeInTheDocument();
    await expect(canvas.getByRole('heading', { level: 2, name: ONBOARDING_DOC_SETTING_TITLE })).toBeInTheDocument();

    // 세 선택 구역이 각자 radiogroup으로 선다
    await expect(canvas.getByRole('radiogroup', { name: INFO_CATEGORY_FIELD_LABEL })).toBeInTheDocument();
    await expect(canvas.getByRole('radiogroup', { name: DOC_KIND_FIELD_LABEL })).toBeInTheDocument();
    await expect(canvas.getByRole('radiogroup', { name: TONE_STYLE_FIELD_LABEL })).toBeInTheDocument();

    await expect(canvas.getByText('0/20')).toBeInTheDocument();

    // 이름 상한(백엔드 1~20자) — 초과 붙여넣기는 입력에서 잘려 올라간다
    const nameInput = canvas.getByRole('textbox', { name: WIKI_NAME_FIELD.label });
    await expect(nameInput).toHaveAttribute('maxlength', String(WIKI_NAME_FIELD.maxLength));
    await userEvent.click(nameInput);
    await userEvent.paste('가'.repeat(WIKI_NAME_FIELD.maxLength + 10));
    await expect(args.onNameChange).toHaveBeenCalledWith('가'.repeat(WIKI_NAME_FIELD.maxLength));

    // 상단 바에 뒤로가기가 있고, 더보기는 콜백이 없으면 그리지 않는다(죽은 버튼 방지)
    await expect(canvas.getByRole('button', { name: '뒤로 가기' })).toBeInTheDocument();
    await expect(canvas.queryByRole('button', { name: '더보기' })).not.toBeInTheDocument();

    // 1단계에는 하단 이전 버튼이 없다(시안대로) — 다음 버튼만
    await expect(canvas.queryByRole('button', { name: '이전' })).not.toBeInTheDocument();
    await userEvent.click(canvas.getByRole('button', { name: ONBOARDING_NEXT_LABEL }));
    await expect(onNext).toHaveBeenCalled();
  },
};

/** 필수 입력이 덜 찬 상태. 보낼 수 없는 요청을 만들지 않게 다음 버튼이 잠긴다. */
export const NextLockedUntilRequiredFilled: Story = {
  args: { ...baseArgs, nextDisabled: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('button', { name: ONBOARDING_NEXT_LABEL })).toBeDisabled();
  },
};
