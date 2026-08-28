import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  INFO_CATEGORY_FIELD_LABEL,
  PURPOSE_FIELD_LABEL,
  WIKI_INFO_CATEGORIES,
  WIKI_PURPOSE_OPTIONS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import PurposeSelectField from './PurposeSelectField';

const baseArgs = {
  categoryLabel: INFO_CATEGORY_FIELD_LABEL,
  categories: WIKI_INFO_CATEGORIES,
  selectedCategoryId: WIKI_INFO_CATEGORIES[0].id,
  onSelectCategory: fn(),
  purposeLabel: PURPOSE_FIELD_LABEL,
  purposeOptions: WIKI_PURPOSE_OPTIONS,
  selectedPurposeId: WIKI_PURPOSE_OPTIONS[0].id,
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
      states: ['default', 'disabled-categories-keep-selection'],
      dataNotes: [
        '**8/14 시안 갱신으로 전면 재설계됐다.** 기존 구조(목적 4옵션 리스트 + 후속 질문 텍스트 입력 0/500)는 소멸하고, 정보 카테고리 칩 6종 + 목적 선택 5종으로 교체됐다.',
        '**목적 선택지는 카테고리에 종속되지 않는다**(8/14 사용자 확정). 시안이 VOC를 고른 상태만 그려 한때 카테고리별 목록으로 구현했는데, 갈린다는 근거가 없었고 칩을 바꿀 때마다 목적 구역이 통째로 사라지는 문제가 있었다.',
        '**지금은 VOC 칩만 고를 수 있다**(8/19 사용자 확정). 나머지 5종은 앞으로 열릴 자리라 숨기지 않고 비활성으로 노출하며, 비활성 표현은 2단계 백필 선택지와 같은 `disabled` 플래그다.',
      ],
      layoutNotes: [
        '목적 구역은 좌측 세로선(2px 점선) + 분기 아이콘 + 내용. 들여쓰기 가이드 폭 32의 중앙에 선이 지나고, 내용은 그로부터 16 떨어진다.',
        '목적 3열 그리드 — 시안 옵션 폭 309.33은 (960−32)/3의 결과값이라 고정하지 않는다.',
      ],
      tokenNotes: [
        '선택 칩 = bg-accent-black-lighten(#46474C) + text-text-normal-inverse, 미선택 테두리 line-normal-neutral(#EAEBEC). **shared Chip을 쓰지 않았다** — Chip의 square/capsule selected는 파랑·초록 계열이라 시안의 검정 칩과 맞지 않고, 공유 계약을 이 화면 때문에 바꿀 수 없다.',
        '**칩 아이콘은 6종이 전부 다르다**(support_agent·lightbulb·shield·client·database·group) — REST 실측으로 확인했고 모두 기존 자산이다. 미지 icon 값은 tag로 떨어뜨린다.',
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

    // VOC 하나만 고를 수 있고 나머지 5종은 자리만 지킨다
    const categoryChips = within(categoryGroup).getAllByRole('radio');
    await expect(categoryChips.filter((chip) => !chip.hasAttribute('disabled'))).toHaveLength(1);
    await expect(canvas.getByRole('radio', { name: /고객 문의 \(VOC\)/ })).toBeEnabled();
    for (const category of WIKI_INFO_CATEGORIES.filter((item) => item.disabled)) {
      await expect(canvas.getByRole('radio', { name: categoryNamePattern(category.label) })).toBeDisabled();
    }
  },
};

/** 라벨의 괄호가 정규식으로 새지 않게 감싼다 — "고객 문의 (VOC)" */
function categoryNamePattern(label: string) {
  return new RegExp(label.replace(/[()]/g, '\\$&'));
}

function CategoryPlayground() {
  const [categoryId, setCategoryId] = useState<string | null>(WIKI_INFO_CATEGORIES[0].id);
  const [purposeId, setPurposeId] = useState<string | null>(WIKI_PURPOSE_OPTIONS[0].id);

  return (
    <PurposeSelectField
      {...baseArgs}
      selectedCategoryId={categoryId}
      onSelectCategory={setCategoryId}
      selectedPurposeId={purposeId}
      onSelectPurpose={setPurposeId}
    />
  );
}

/** 비활성 칩을 눌러도 선택이 넘어가지 않고, 목적 구역은 카테고리와 무관하게 남는다 */
export const DisabledCategoriesKeepSelection: Story = {
  args: baseArgs,
  render: () => <CategoryPlayground />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    for (const category of WIKI_INFO_CATEGORIES) {
      await userEvent.click(canvas.getByRole('radio', { name: categoryNamePattern(category.label) }));

      const purposeGroup = canvas.getByRole('radiogroup', { name: PURPOSE_FIELD_LABEL });
      await expect(within(purposeGroup).getAllByRole('radio')).toHaveLength(5);

      // 비활성 칩을 눌러도 선택은 VOC에 남는다
      await expect(canvas.getByRole('radio', { name: /고객 문의 \(VOC\)/ })).toHaveAttribute('aria-checked', 'true');
    }

    await expect(canvas.getByRole('radio', { name: WIKI_PURPOSE_OPTIONS[0].label })).toHaveAttribute(
      'aria-checked',
      'true',
    );
  },
};
