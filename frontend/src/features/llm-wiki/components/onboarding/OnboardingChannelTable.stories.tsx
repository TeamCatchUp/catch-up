import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

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
      states: ['default', 'loading', 'empty', 'error', 'narrow-slot'],
      dataNotes: [
        '행 카피(채널명·2025-01-23)는 시안 필러라 카피 미정(TBD) — 스토리명에 반영.',
        '채널 mock은 백엔드 ChannelListItemResponse(id·name·workspace_id·is_admin·document_count·folders) 모양을 지킨다. "최근 수정일"은 대응 API 필드가 없어 [SPEC] 별도 필드로 격리(감사 §3 백엔드 계약 갭).',
        '⚠️ 로딩·빈·에러는 Figma 근거가 없다 — 2026-08-13 사용자 승인으로 구현했다(로딩은 스켈레톤 지정, 빈·에러는 구현 재량 위임). 디자이너 승인본이 아니므로 시안이 도착하면 교체 대상이다.',
        '선택 표시는 여전히 미구현 — 시안 UNKNOWN(감사 §7).',
      ],
      interactionNotes: [
        '빈 상태는 ready + 행 0으로 판정한다. 로딩과 구분되는 지점이 그것뿐이라 별도 status 값을 두지 않았다.',
        '에러의 재시도 버튼은 onRetry가 있을 때만 뜬다 — 재시도 동선이 없는 화면에서 죽은 버튼을 만들지 않기 위해서다(NavTree·AvatarGroup 선례).',
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

    // 수정일 열은 우측 정렬 (8/14 시안에서 표기가 점 구분으로 바뀌었다)
    const dateCell = within(firstBodyRow).getByText(ONBOARDING_CHANNEL_ROWS[0].lastModifiedLabel);
    await expect(getComputedStyle(dateCell).textAlign).toBe('right');
  },
};

/** 로딩 스켈레톤. 데이터 표와 열 상수를 공유해 로드 후 열이 움직이지 않는지까지 본다 */
export const Loading: Story = {
  args: { headers: CHANNEL_TABLE_HEADERS, rows: [], status: 'loading' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const skeleton = canvas.getByRole('status', { name: '채널 목록 불러오는 중' });

    // 표 시맨틱은 내용이 없을 때 AT에 잡음이라 쓰지 않는다
    await expect(canvas.queryByRole('table')).not.toBeInTheDocument();

    // 승인 안 된 카피를 넣지 않았는지 — 골격에는 글자가 없어야 한다
    await expect(skeleton.textContent).toBe('');

    // 헤더 줄 + 행 5줄이 같은 열 템플릿을 쓴다(로드 후 레이아웃 점프 방지)
    const gridRows = Array.from(skeleton.children);
    await expect(gridRows).toHaveLength(6);
    const templates = new Set(gridRows.map((row) => getComputedStyle(row).gridTemplateColumns));
    await expect(templates.size).toBe(1);
  },
};

/** 아직 고른 채널이 없는 상태. 8/14에 표가 "선택 결과"임이 확정돼 문구가 바뀌었다 */
export const Empty: Story = {
  args: { headers: CHANNEL_TABLE_HEADERS, rows: [], status: 'ready' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('아직 선택한 채널이 없습니다')).toBeInTheDocument();
    await expect(canvas.queryByRole('table')).not.toBeInTheDocument();

    // 연동·생성 유도 문구는 넣지 않았다 — 그 동선은 아직 제품 결정이 아니다
    await expect(canvas.queryByRole('button')).not.toBeInTheDocument();
  },
};

export const Error: Story = {
  args: { headers: CHANNEL_TABLE_HEADERS, rows: [], status: 'error', onRetry: fn() },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('alert')).toHaveTextContent('채널 목록을 불러오지 못했습니다');

    await userEvent.click(canvas.getByRole('button', { name: '다시 시도' }));
    await expect(args.onRetry).toHaveBeenCalled();
  },
};

/** onRetry 없이 렌더하면 버튼이 사라진다 — 죽은 버튼 방지 계약 */
export const ErrorWithoutRetry: Story = {
  args: { headers: CHANNEL_TABLE_HEADERS, rows: [], status: 'error' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('alert')).toBeInTheDocument();
    await expect(canvas.queryByRole('button')).not.toBeInTheDocument();
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
