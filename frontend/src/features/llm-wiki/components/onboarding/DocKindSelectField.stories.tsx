import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  DOC_KIND_FIELD_LABEL,
  DOC_KIND_SAMPLE_CAPTION,
  DOC_KIND_SAMPLE_TITLE,
  WIKI_DOC_KIND_PRESETS,
} from '../../fixtures/llmWikiOnboardingFixtures';
import { WIKI_DOC_TEMPLATE_SAMPLES } from '../../fixtures/llmWikiTemplateSamples';
import DocKindSelectField from './DocKindSelectField';

const baseArgs = {
  label: DOC_KIND_FIELD_LABEL,
  presets: WIKI_DOC_KIND_PRESETS,
  selectedId: WIKI_DOC_KIND_PRESETS[0].id,
  onSelect: fn(),
  sampleTitle: DOC_KIND_SAMPLE_TITLE,
  sampleCaption: DOC_KIND_SAMPLE_CAPTION,
  sampleText: WIKI_DOC_TEMPLATE_SAMPLES[WIKI_DOC_KIND_PRESETS[0].id],
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
        '**8/14 시안 갱신으로 항목이 전면 교체됐다.** 기존 4종(용어집·팀/인물·서비스 개요·의사결정 이력) → 6종(기능 요청·고객 불편사항·자주 묻는 질문·고객사별 요청사항·고객사 히스토리·정책 예외사항). 라벨·설명 모두 실카피이고, 8/13 감사가 지적한 설명 복붙 문제는 해당 항목 소멸로 해소됐다.',
        '우측 패널 제목이 "예시 문장" → "템플릿 예시"로 바뀌고, 목적 오해 방지 카피가 이 헤더 우측으로 이동했다.',
        '**패널 본문은 문서 양식 6종의 마크다운이다**(Confluence 163282945 원문, 종류와 1:1). 필러가 아니라 실제 양식이고, 부모가 선택된 종류의 양식을 넘긴다.',
        '표·인용·코드 칩이 있어 공용 `markdown-body` + remarkGfm으로 렌더한다 — 채팅·에디터가 쓰는 그 규격이다.',
      ],
      layoutNotes: [
        '좌 리스트:우 패널 = 400:606 비율(grid-cols-[400fr_606fr]) — px 고정 대신 비율로 옮겼다.',
        '리스트에 스크롤이 실재한다(시안 scrollbar 노드). max-h-125 + overflow-y-auto, 항목은 shrink-0.',
      ],
      tokenNotes: [
        '아이콘 6종 중 request·client는 8/14 Figma에서 새로 받아 추가했다 — 20×20 그리드로 감싸고 fill을 currentColor로 정규화(리포 관례). 나머지 4종은 기존 자산 재사용.',
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
    await expect(radios).toHaveLength(6);
    await expect(radios[0]).toHaveAttribute('aria-checked', 'true');

    await expect(canvas.getByText(DOC_KIND_SAMPLE_TITLE)).toBeInTheDocument();
    await expect(canvas.getByText(DOC_KIND_SAMPLE_CAPTION)).toBeInTheDocument();

    // 좌우 2열이 유지되는지 — 세로로 무너지면 x가 같아진다
    const list = radios[0].closest('[role="radiogroup"]')!;
    const panel = canvas.getByText(DOC_KIND_SAMPLE_TITLE).parentElement!;
    await expect(list.getBoundingClientRect().left).toBeLessThan(panel.getBoundingClientRect().left);

    // 6개가 스크롤 안에 들어간다 — 목록이 카드 밖으로 흘러넘치면 안 된다
    await expect(list.scrollHeight).toBeGreaterThan(list.clientHeight);
  },
};

/** 좁은 슬롯에서 카드가 수습되는지 — grid 비율이 px로 박히면 여기서 넘친다 */
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
