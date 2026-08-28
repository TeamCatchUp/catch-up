import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  TONE_SAMPLE_TAG_LABEL,
  TONE_STYLE_FIELD_LABEL,
  WIKI_TONE_STYLE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import ToneStyleField from './ToneStyleField';

const baseArgs = {
  label: TONE_STYLE_FIELD_LABEL,
  options: WIKI_TONE_STYLE_OPTIONS,
  selectedId: WIKI_TONE_STYLE_OPTIONS[0].id,
  onSelect: fn(),
  sampleTagLabel: TONE_SAMPLE_TAG_LABEL,
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
        '**8/14 시안 갱신으로 재설계됐다.** 기존(썸네일 이미지 4장 + 체크박스 + 커스텀 작성 입력 0/500) → 3열 카드 3종에 설명과 예시 문장이 붙었다. 4번째 문체("의사결정 이력")와 커스텀 입력은 소멸.',
        '**예시 문장 3종이 실카피로 확보됐다** — 8/13 감사의 카피 미정(TBD)이 여기서 해소됐다.',
        '선택 표시가 checkbox → check_circle로 바뀌었다. 다중 선택이 아니라 단일 선택이라는 뜻이라 selectedIds(배열) → selectedId(단수)로 계약을 좁혔다.',
      ],
      layoutNotes: ['3열 grid-cols-3 gap-4 — 시안 카드 폭 325.33은 (1008−32)/3의 결과값이라 고정하지 않는다.'],
      tokenNotes: [
        '"예시" 태그 = bg-accent-light-blue-neutral(#C4ECFE) + radius 6(rounded-md2). shared Badge에 light-blue variant가 없어 span으로 그렸다.',
        '미선택 체크 아이콘은 icon-normal-assistive(#CDD1D5) — 선택 카드 defs와 대조해 확인했다.',
      ],
    }),
  },
} satisfies Meta<typeof ToneStyleField>;

export default meta;
type Story = StoryObj<typeof ToneStyleField>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = canvas.getAllByRole('radio');
    await expect(radios).toHaveLength(3);
    await expect(radios[0]).toHaveAttribute('aria-checked', 'true');
    await expect(radios[1]).toHaveAttribute('aria-checked', 'false');

    // 카드마다 자기 예시 문장을 갖는다 — 8/14에 확보된 실카피
    await expect(canvas.getByText(WIKI_TONE_STYLE_OPTIONS[0].sampleText)).toBeInTheDocument();
    await expect(canvas.getByText(WIKI_TONE_STYLE_OPTIONS[2].sampleText)).toBeInTheDocument();
    await expect(canvas.getAllByText(TONE_SAMPLE_TAG_LABEL)).toHaveLength(3);

    // 3열이 유지되는지 — 첫 카드와 둘째 카드가 같은 행에 있어야 한다
    const [first, second] = radios;
    await expect(first.getBoundingClientRect().top).toBe(second.getBoundingClientRect().top);
  },
};
