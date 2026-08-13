import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { CHANNEL_TABLE_HEADERS, ONBOARDING_CHANNEL_ROWS } from '../../fixtures/llmWikiOnboardingFixtures';
import OnboardingChannelTable from './OnboardingChannelTable';

const meta = {
  title: 'Compositions/LLM Wiki/Onboarding/OnboardingChannelTable',
  component: OnboardingChannelTable,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'llm-wiki',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18071-84469',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18071:84469',
      },
      viewport: { width: 1008 },
      states: ['default', 'narrow-slot'],
      dataNotes: [
        '행 카피(채널명·2025-01-23)는 시안 필러라 카피 미정(TBD) — 스토리명에 반영.',
        '채널 mock은 백엔드 ChannelListItemResponse(id·name·workspace_id·is_admin·document_count·folders) 모양을 지킨다. "최근 수정일"은 대응 API 필드가 없어 [SPEC] 별도 필드로 격리(감사 §3 백엔드 계약 갭).',
        '선택 표시·빈 목록·로딩·에러 상태 스토리는 만들지 않는다 — 디자인 MISSING/UNKNOWN(감사 §7).',
      ],
      layoutNotes: [
        '열 템플릿은 onboardingChannelTableGrid 상수 하나를 헤더·행이 공유한다 — 행별 독립 grid라 상수 없이는 열이 드리프트한다.',
        '시안 두 열(채널명·최근 수정일)은 폭을 절반씩 나눈다 → minmax(0,1fr) 2개. 수정일 열은 우측 정렬.',
        '행 높이 47은 결과값(py-3 + 본문 23)이라 h-*로 고정하지 않는다.',
      ],
    }),
  },
} satisfies Meta<typeof OnboardingChannelTable>;

export default meta;
type Story = StoryObj<typeof OnboardingChannelTable>;

export const DefaultCopyTBD: Story = {
  args: { headers: CHANNEL_TABLE_HEADERS, rows: ONBOARDING_CHANNEL_ROWS },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getAllByRole('columnheader')).toHaveLength(2);
    await expect(canvas.getAllByRole('row')).toHaveLength(6);

    // 헤더·본문 행이 같은 열 템플릿을 쓰는지 — 상수 공유가 깨지면 여기서 갈린다
    const [headerRow, firstBodyRow] = canvas.getAllByRole('row');
    await expect(getComputedStyle(headerRow).gridTemplateColumns).toBe(
      getComputedStyle(firstBodyRow).gridTemplateColumns,
    );

    // 수정일 열은 우측 정렬
    const dateCell = within(firstBodyRow).getByText('2025-01-23');
    await expect(getComputedStyle(dateCell).textAlign).toBe('right');
  },
};

/** 좁은 슬롯에서 채널명이 truncate로 수습되는지 — 이름 셀이 절대폭이면 여기서 넘친다 */
export const NarrowSlot: Story = {
  args: { headers: CHANNEL_TABLE_HEADERS, rows: ONBOARDING_CHANNEL_ROWS },
  render: (args) => (
    <div className="w-100">
      <OnboardingChannelTable {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const nameSpan = canvas.getAllByText(ONBOARDING_CHANNEL_ROWS[0].channel.name)[0];
    await expect(nameSpan.scrollWidth).toBeGreaterThan(nameSpan.clientWidth);
  },
};
