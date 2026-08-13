import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  DOC_KIND_FIELD_LABEL,
  DOC_KIND_SAMPLE_TITLE,
  WIKI_DOC_KIND_PRESETS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import DocKindSelectField from './DocKindSelectField';

const baseArgs = {
  label: DOC_KIND_FIELD_LABEL,
  presets: WIKI_DOC_KIND_PRESETS,
  selectedId: WIKI_DOC_KIND_PRESETS[0].id,
  onSelect: fn(),
  sampleTitle: DOC_KIND_SAMPLE_TITLE,
  sampleText: WIKI_DOC_KIND_PRESETS[0].sampleText,
};

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/DocKindSelectField',
  component: DocKindSelectField,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18047-99875',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18047:99875',
      },
      viewport: { width: 1008 },
      states: ['default', 'narrow-slot'],
      dataNotes: [
        '프리셋 4종 라벨·설명은 시안 실카피. 단 "의사결정 이력" 설명이 "서비스 개요"와 동일한 복붙 카피(카피 미정 신호, design-request 참조).',
        '예시 문장은 앞 문장만 실카피이고 뒷부분은 시안 필러(TBD). 선택 변경 시 예시가 바뀌는지는 시안에 한 상태뿐이라 미확정 — sampleText를 부모가 주도록 뒀다.',
      ],
      layoutNotes: [
        '좌 리스트:우 패널 = 400:606 ≈ 2fr:3fr — px 고정 대신 비율로 옮겼다. 패널은 border-l로 가른다.',
        '옵션 카드 111은 결과값(p-4 + 라벨 23 + gap + 설명 2줄)이라 h-*로 고정하지 않는다.',
      ],
      tokenNotes: [
        '종류 아이콘 4종(file·group·graph·search_file)은 기존 public 자산 재사용 — 신규 다운로드 0. 미지 icon 값은 file로 떨어뜨린다(열린 타입 규칙).',
      ],
    }),
  },
} satisfies Meta<typeof DocKindSelectField>;

export default meta;
type Story = StoryObj<typeof DocKindSelectField>;

export const Default: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const radios = canvas.getAllByRole('radio');
    await expect(radios).toHaveLength(4);
    await expect(radios[0]).toHaveAttribute('aria-checked', 'true');

    await expect(canvas.getByText(DOC_KIND_SAMPLE_TITLE)).toBeInTheDocument();
    await expect(canvas.getByText(WIKI_DOC_KIND_PRESETS[0].sampleText)).toBeInTheDocument();

    // 좌우 2열이 유지되는지 — 리스트와 패널이 세로로 무너지면 x가 같아진다
    const list = radios[0].closest('[role="radiogroup"]')!;
    const panel = canvas.getByText(DOC_KIND_SAMPLE_TITLE).parentElement!;
    await expect(list.getBoundingClientRect().left).toBeLessThan(panel.getBoundingClientRect().left);
  },
};

/** 좁은 슬롯에서 카드 설명·라벨이 수습되는지 — grid 비율이 px로 박히면 여기서 넘친다 */
export const NarrowSlot: Story = {
  args: baseArgs,
  render: (args) => (
    <div className="w-160">
      <DocKindSelectField {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const field = canvas.getAllByRole('radio')[0].closest('div.flex.w-full')!;
    await expect(field.scrollWidth).toBeLessThanOrEqual(field.clientWidth + 1);
  },
};
