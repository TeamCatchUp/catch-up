import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  FOLLOW_UP_PLACEHOLDER_TBD,
  TONE_CUSTOM_MAX_LENGTH,
  TONE_CUSTOM_OPTION,
  TONE_STYLE_FIELD_LABEL,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import ToneStyleField from './ToneStyleField';

const baseArgs = {
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
};

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/ToneStyleField',
  component: ToneStyleField,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18071-47202',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18071:47202',
      },
      viewport: { width: 1008 },
      states: ['default'],
      dataNotes: [
        '카드 라벨 4종은 시안 실카피 — 단 4번째 "의사결정 이력"이 문서 종류 항목명과 중복(카피 미정 신호, design-request 참조).',
        '커스텀 설명은 프리셋 설명과 동일한 복붙 필러 추정(TBD). 커스텀 입력 placeholder도 시안 필러 유지.',
        '체크박스형이지만 시안에는 1개 선택 상태만 있다 — 다중 허용 여부 미확정이라 선택을 목록 props로 받는다.',
      ],
      layoutNotes: [
        '카드 4열 = grid-cols-4 gap-6(시안 열 간격 24). 카드 폭 234는 1008 4등분의 결과값이라 고정하지 않는다.',
        '썸네일 140 = h-35 고정 — 시안에서도 빈 자리 표시라 배경(bg-fill-normal-strong)만 그린다. 체크박스는 우상단 absolute.',
      ],
      reuseNotes: ['체크박스는 shared CheckboxIcon 재사용 — 선택 파랑(icon-primary-normal)이 DS와 일치한다.'],
    }),
  },
} satisfies Meta<typeof ToneStyleField>;

export default meta;
type Story = StoryObj<typeof ToneStyleField>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const checkboxes = canvas.getAllByRole('checkbox');
    await expect(checkboxes).toHaveLength(4);
    await expect(checkboxes[0]).toHaveAttribute('aria-checked', 'true');
    await expect(checkboxes[1]).toHaveAttribute('aria-checked', 'false');

    await expect(canvas.getByText(TONE_CUSTOM_OPTION.label)).toBeInTheDocument();
    await expect(canvas.getByText('0/500')).toBeInTheDocument();

    // 썸네일 높이 140 고정 — 시안의 빈 썸네일 자리 규격
    const thumbnail = checkboxes[0].querySelector('span.relative')!;
    await expect(Math.round(thumbnail.getBoundingClientRect().height)).toBe(140);
  },
};
