import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  INFO_CATEGORY_FIELD_LABEL,
  PURPOSE_FIELD_LABEL,
  WIKI_INFO_CATEGORIES,
} from '../../fixtures/llmWikiOnboardingFixtures';
import PurposeSelectField from './PurposeSelectField';

const baseArgs = {
  categoryLabel: INFO_CATEGORY_FIELD_LABEL,
  categories: WIKI_INFO_CATEGORIES,
  selectedCategoryId: WIKI_INFO_CATEGORIES[0].id,
  onSelectCategory: fn(),
  purposeLabel: PURPOSE_FIELD_LABEL,
  selectedPurposeId: WIKI_INFO_CATEGORIES[0].purposeOptions[0].id,
  onSelectPurpose: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18258-63577',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18258:63577',
      },
      viewport: { width: 1008 },
      states: ['default', 'category-switch', 'category-without-purposes'],
      dataNotes: [
        '**8/14 시안 갱신으로 전면 재설계됐다.** 기존 구조(목적 4옵션 리스트 + 후속 질문 텍스트 입력 0/500)는 소멸하고, 정보 카테고리 칩 6종 + 카테고리별 목적 선택 5종으로 교체됐다.',
        '카테고리 6종·목적 5종은 시안 실카피. 단 시안은 "고객 문의 (VOC)"를 고른 상태만 그려서 **나머지 5개 카테고리의 목적 목록은 미도시** — 픽스처를 빈 배열로 두고 목적 구역을 접는다(발명 금지).',
      ],
      layoutNotes: [
        '목적 구역은 좌측 세로선(border-l) + 분기 아이콘 + 내용. 시안 들여쓰기 32 = pl-8, 아이콘~내용 16 = pl-4.',
        '목적 3열 그리드 — 시안 옵션 폭 301.33은 (936−32)/3의 결과값이라 고정하지 않는다.',
      ],
      tokenNotes: [
        '선택 칩 = bg-accent-black-lighten(#46474C) + text-text-normal-inverse. **shared Chip을 쓰지 않았다** — Chip의 square/capsule selected는 파랑·초록 계열이라 시안의 검정 칩과 맞지 않고, 공유 계약을 이 화면 때문에 바꿀 수 없다.',
        '분기 아이콘은 시안 자산명이 확인되지 않아 arrow_right2로 대체했다(감사 §7).',
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

    // 카테고리 칩 6개 + 목적 5개가 각각 독립 radiogroup이다
    const categoryGroup = canvas.getByRole('radiogroup', { name: INFO_CATEGORY_FIELD_LABEL });
    await expect(within(categoryGroup).getAllByRole('radio')).toHaveLength(6);

    const purposeGroup = canvas.getByRole('radiogroup', { name: PURPOSE_FIELD_LABEL });
    await expect(within(purposeGroup).getAllByRole('radio')).toHaveLength(5);

    await expect(canvas.getByRole('radio', { name: /고객 문의 \(VOC\)/ })).toHaveAttribute('aria-checked', 'true');
  },
};

/** 카테고리를 바꾸면 목적 목록이 함께 갈린다 — 미도시 카테고리는 구역 자체가 접힌다 */
function CategoryPlayground() {
  const [categoryId, setCategoryId] = useState<string | null>(WIKI_INFO_CATEGORIES[0].id);
  const [purposeId, setPurposeId] = useState<string | null>(WIKI_INFO_CATEGORIES[0].purposeOptions[0].id);

  return (
    <PurposeSelectField
      {...baseArgs}
      selectedCategoryId={categoryId}
      onSelectCategory={(id) => {
        setCategoryId(id);
        setPurposeId(WIKI_INFO_CATEGORIES.find((c) => c.id === id)?.purposeOptions[0]?.id ?? null);
      }}
      selectedPurposeId={purposeId}
      onSelectPurpose={setPurposeId}
    />
  );
}

export const CategorySwitchCollapsesPurposes: Story = {
  args: baseArgs,
  render: () => <CategoryPlayground />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('radiogroup', { name: PURPOSE_FIELD_LABEL })).toBeInTheDocument();

    // 목적이 미도시인 카테고리로 옮기면 구역이 사라진다(빈 목록을 그리지 않는다)
    await userEvent.click(canvas.getByRole('radio', { name: /제품과 기획/ }));
    await expect(canvas.queryByRole('radiogroup', { name: PURPOSE_FIELD_LABEL })).not.toBeInTheDocument();
  },
};

/** 목적 목록이 미도시인 카테고리(감사 UNKNOWN) — 접힌 상태를 고정한다 */
export const CategoryWithoutPurposesTBD: Story = {
  args: { ...baseArgs, selectedCategoryId: 'product', selectedPurposeId: null },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('radio', { name: /제품과 기획/ })).toHaveAttribute('aria-checked', 'true');
    await expect(canvas.queryByRole('radiogroup', { name: PURPOSE_FIELD_LABEL })).not.toBeInTheDocument();
  },
};
