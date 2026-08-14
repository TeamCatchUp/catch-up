import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { ONBOARDING_STEPS } from '../../fixtures/llmWikiOnboardingFixtures';
import OnboardingStepper from './OnboardingStepper';

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/OnboardingStepper',
  component: OnboardingStepper,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18071-83328',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18071:83328',
      },
      viewport: { width: 1072, height: 46 },
      states: ['step1-active', 'step2-active', 'narrow-slot'],
      dataNotes: [
        '단계 라벨 3종(위키의 목적 설정·수집 위치 설정·완료)은 시안 실카피.',
        '"3 완료" 화면 자체는 Figma에 없다(감사 MISSING) — 스테퍼는 라벨만 안다.',
      ],
      layoutNotes: [
        '컨테이너 46 = p-1(4×2) + 세그먼트 38(py-1.5 + 번호 원 26). 세그먼트 폭은 flex-1 균등 분할 — 시안 353.33은 1064/3의 결과값이라 고정하지 않는다.',
        '번호 원 26 = size-6.5, 원-라벨 간격 12 = gap-3(시안 라벨 x50 - 원 끝 38).',
      ],
      tokenNotes: [
        '컨테이너 bg-fill-normal-strong(#F7F7F8), 활성 필 bg-fill-normal-normal + shadow-card — 다크 시안(1단계)에서는 같은 토큰의 다크 값(#292A2D 위 #1B1C1E 필)으로 자동 대응. 컨테이너 테두리는 확대에서도 판별 불가라 그리지 않았다(디자이너 확인 대상).',
        '활성 텍스트 text-text-normal-strong, 비활성 text-text-normal-alternative. 번호 원 배경은 활성=strong/비활성=normal로 배경과 반전 — 확대 스크린샷 대조로 추정한 매핑이라 디자이너 확인 대상.',
      ],
    }),
  },
} satisfies Meta<typeof OnboardingStepper>;

export default meta;
type Story = StoryObj<typeof OnboardingStepper>;

export const PurposeStepActive: Story = {
  args: { steps: ONBOARDING_STEPS, currentStep: 1 },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const items = canvas.getAllByRole('listitem');
    await expect(items).toHaveLength(3);

    // aria-current가 활성 단계를 가리키고, 활성 필만 배경이 다르다
    await expect(items[0]).toHaveAttribute('aria-current', 'step');
    await expect(items[1]).not.toHaveAttribute('aria-current');
    const activeBg = getComputedStyle(items[0]).backgroundColor;
    await expect(activeBg).not.toBe(getComputedStyle(items[1]).backgroundColor);

    const list = canvas.getByRole('list');
    await expect(getComputedStyle(list).borderRadius).toBe('12px');
    // 시안 프레임 46 = padding 4×2 + 세그먼트 38. 테두리 1px가 그 밖에 얹혀 48이 된다
    await expect(Math.round(list.getBoundingClientRect().height)).toBe(48);
  },
};

export const SourceStepActive: Story = {
  args: { steps: ONBOARDING_STEPS, currentStep: 2 },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const items = canvas.getAllByRole('listitem');
    await expect(items[1]).toHaveAttribute('aria-current', 'step');
    await expect(items[0]).not.toHaveAttribute('aria-current');
  },
};

/** 좁은 슬롯에서 라벨이 truncate로 수습되는지 — 세그먼트에 px 폭이 박히면 여기서 넘친다 */
export const NarrowSlot: Story = {
  args: { steps: ONBOARDING_STEPS, currentStep: 1 },
  render: (args) => (
    <div className="w-90">
      <OnboardingStepper {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const list = canvas.getByRole('list');
    await expect(list.scrollWidth).toBeLessThanOrEqual(list.clientWidth + 1);
  },
};
