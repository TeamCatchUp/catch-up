import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  FOLLOW_UP_EXAMPLE,
  FOLLOW_UP_MAX_LENGTH,
  FOLLOW_UP_PLACEHOLDER_TBD,
  PURPOSE_FIELD_CAPTION,
  PURPOSE_FIELD_LABEL,
  WIKI_PURPOSE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import PurposeSelectField from './PurposeSelectField';

const baseArgs = {
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
};

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/PurposeSelectField',
  component: PurposeSelectField,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18047-99824',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18047:99824',
      },
      viewport: { width: 1008 },
      states: ['default', 'selection-moves-follow-up', 'custom-selected'],
      dataNotes: [
        '목적 3종·후속 질문 3종·우측 캡션(오해 방지 문구)·예시 캡션은 시안 실카피.',
        '후속 입력 placeholder는 시안이 "text text…" 필러라 카피 미정(TBD) — 임의 작문하지 않았다.',
        '옵션↔후속 질문 매핑은 시안 섹션의 나열 순서 대응으로 추정 — 디자이너 확인 대상(감사 §5).',
      ],
      layoutNotes: [
        '옵션 행 56 = h-14, 리스트는 border + divide-y. 후속 패널 p-5, 내부 입력 박스 p-4 — 시안 오프셋(옵션 y37, 패널 y250)에서 유도.',
        '검증 실패 표시·글자수 초과 상태는 그리지 않는다(감사 MISSING). maxLength 상한만 시각 무변경 안전장치로 건다.',
      ],
      tokenNotes: [
        '선택 아이콘 check_circle_filled = text-icon-primary-normal, 미선택 check_circle = text-icon-normal-alternative(#B1B8BE — 1단계 defs Icon/Normal/Alternative).',
        '후속 패널 bg-fill-normal-strong, 내부 입력 박스 bg-fill-normal-normal — 다크 시안에서 패널 #292A2D/박스 #1B1C1E 대비가 같은 토큰으로 재현된다.',
      ],
    }),
  },
} satisfies Meta<typeof PurposeSelectField>;

export default meta;
type Story = StoryObj<typeof PurposeSelectField>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = canvas.getAllByRole('radio');
    await expect(radios).toHaveLength(4);
    await expect(radios[0]).toHaveAttribute('aria-checked', 'true');
    await expect(radios[1]).toHaveAttribute('aria-checked', 'false');

    // 첫 옵션의 후속 질문과 카운터가 함께 노출된다
    await expect(canvas.getByText('주로 어떤 업무를 맡고 있나요?')).toBeInTheDocument();
    await expect(canvas.getByText('0/500')).toBeInTheDocument();
    await expect(canvas.getByText(PURPOSE_FIELD_CAPTION)).toBeInTheDocument();
  },
};

/** 제어 컴포넌트 확인용 래퍼 — 선택을 바꾸면 후속 질문이 함께 갈린다 */
function SelectionPlayground() {
  const [selectedId, setSelectedId] = useState<string | null>(WIKI_PURPOSE_OPTIONS[0].id);
  const [followUpValue, setFollowUpValue] = useState('');

  return (
    <PurposeSelectField
      {...baseArgs}
      selectedId={selectedId}
      onSelect={setSelectedId}
      followUpValue={followUpValue}
      onFollowUpChange={setFollowUpValue}
    />
  );
}

export const SelectionMovesFollowUp: Story = {
  args: baseArgs,
  render: () => <SelectionPlayground />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('radio', { name: WIKI_PURPOSE_OPTIONS[1].label }));
    await expect(canvas.getByText('어떤 문의를 자주 받나요?')).toBeInTheDocument();
    await expect(canvas.queryByText('주로 어떤 업무를 맡고 있나요?')).not.toBeInTheDocument();
  },
};

/** 커스텀 선택 시 후속 UI는 시안에 없다(감사 UNKNOWN) — 패널을 접는 현재 동작을 고정만 한다 */
export const CustomSelectedFollowUpTBD: Story = {
  args: { ...baseArgs, selectedId: 'custom' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('radio', { name: '커스텀 작성하기' })).toHaveAttribute('aria-checked', 'true');
    await expect(canvas.queryByRole('textbox')).not.toBeInTheDocument();
  },
};
