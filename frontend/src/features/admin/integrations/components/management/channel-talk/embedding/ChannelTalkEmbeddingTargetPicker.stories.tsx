import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../../.storybook/catchupStoryParameters';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';
import ChannelTalkEmbeddingTargetPicker from './ChannelTalkEmbeddingTargetPicker';

const DATA_RANGE_OPTIONS = ['전체', '1개월', '3개월', '6개월', '1년'] as const;

const makeChannel = (index: number, documentCount: number): ChannelTalkChannelTarget => ({
  id: `ch-${index}`,
  name: `채널명 text text text text text text ${index}`,
  dataRange: '1개월',
  documentSpaces: Array.from({ length: documentCount }, (_, i) => ({
    id: `ch-${index}-doc-${i}`,
    name: `도큐먼트 스페이스명 text text text ${i}`,
    dataRange: '전체',
  })),
});

// 도큐먼트 수를 3으로 두면 좌 패널의 "전체 3개"(채널 수)와 문구가 겹친다
const CHANNELS: readonly ChannelTalkChannelTarget[] = [makeChannel(1, 8), makeChannel(2, 4), makeChannel(3, 5)];

/** 선택 상태를 들고 있는 스토리 전용 래퍼 — 컴포넌트는 상태를 갖지 않는다 */
function PickerHarness({
  channels = CHANNELS,
  initialSelected = [],
}: {
  channels?: readonly ChannelTalkChannelTarget[];
  initialSelected?: readonly string[];
}) {
  const [activeChannelId, setActiveChannelId] = useState(channels[0]?.id ?? '');
  const [selected, setSelected] = useState<readonly string[]>(initialSelected);
  const [ranges, setRanges] = useState<Record<string, string>>({});

  const withRange = channels.map((channel) => ({
    ...channel,
    dataRange: ranges[channel.id] ?? channel.dataRange,
    documentSpaces: channel.documentSpaces.map((doc) => ({ ...doc, dataRange: ranges[doc.id] ?? doc.dataRange })),
  }));

  const toggleChannel = (channelId: string) => {
    const channel = channels.find((item) => item.id === channelId);
    if (!channel) return;
    const ids = channel.documentSpaces.map((doc) => doc.id);
    const allOn = ids.every((id) => selected.includes(id));
    setSelected((prev) => (allOn ? prev.filter((id) => !ids.includes(id)) : [...new Set([...prev, ...ids])]));
  };

  return (
    // Figma 폼 컨테이너 780, 좌우 여백 32 → 선택기는 정확히 716
    <div className="bg-fill-normal-normal w-195 p-8">
      <ChannelTalkEmbeddingTargetPicker
        channels={withRange}
        activeChannelId={activeChannelId}
        selectedDocumentIds={selected}
        dataRangeOptions={DATA_RANGE_OPTIONS}
        onActiveChannelChange={setActiveChannelId}
        onToggleChannel={toggleChannel}
        onToggleDocument={(_channelId, documentId) =>
          setSelected((prev) =>
            prev.includes(documentId) ? prev.filter((id) => id !== documentId) : [...prev, documentId],
          )
        }
        onChannelDataRangeChange={(channelId, next) => setRanges((prev) => ({ ...prev, [channelId]: next }))}
        onDocumentDataRangeChange={(_channelId, documentId, next) =>
          setRanges((prev) => ({ ...prev, [documentId]: next }))
        }
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkEmbeddingTargetPicker',
  component: ChannelTalkEmbeddingTargetPicker,
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17414-97988',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17414:97988',
      },
      viewport: { width: 780, height: 720 },
      states: ['default', 'partially-selected', 'narrow'],
      layoutNotes: [
        '716×634 = 좌 채널 목록 280 + 우 선택 상세 436. 좌만 고정, 우가 남은 폭을 먹는다.',
        '컬럼 헤더 pl 12 / pr 20 / py 8, gap 32. 좌측 36 스페이서가 체크박스 자리를 비운다.',
        '채널 헤더 67: fill/normal/strong 배경 + line/normal/assistive 아래선. 도큐먼트 행 56.',
        '바깥 테두리·radius는 스크린샷에서 읽었다 — 노드 속성 미확인.',
      ],
      dataNotes: [
        '원래 ChannelTalkEmbeddingModal 이었는데 커넥터 상세 화면 안으로 들어왔다.',
        '데이터 기간 선택지는 Figma에 "1개월"·"전체"만 보여 근거가 없다 — 호출부가 넘긴다.',
      ],
    }),
  },
} satisfies Meta<typeof ChannelTalkEmbeddingTargetPicker>;

export default meta;

type Story = StoryObj<typeof ChannelTalkEmbeddingTargetPicker>;

export const Default: Story = {
  render: () => <PickerHarness />,
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('채널명')).toBeInTheDocument();
    await expect(canvas.getByText('채널&도큐먼트 스페이스명')).toBeInTheDocument();
    await expect(canvas.getByText('전체 3개')).toBeInTheDocument();

    // 채널 헤더 3 + 도큐먼트 17
    await expect(canvas.getAllByRole('checkbox')).toHaveLength(20);

    // 도큐먼트 하나만 켜면 그 채널 헤더가 mixed 가 된다
    const firstDocument = canvas.getAllByRole('checkbox')[1];
    await userEvent.click(firstDocument);
    await expect(canvas.getAllByRole('checkbox')[0]).toHaveAttribute('aria-checked', 'mixed');
    await expect(canvas.getByText('1개 선택됨')).toBeInTheDocument();
  },
};

export const ChannelToggleSelectsAll: Story = {
  render: () => <PickerHarness />,
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    const channelCheckbox = canvas.getAllByRole('checkbox')[0];

    await userEvent.click(channelCheckbox);
    await expect(channelCheckbox).toHaveAttribute('aria-checked', 'true');
    await expect(canvas.getByText('8개 선택됨')).toBeInTheDocument();

    await userEvent.click(channelCheckbox);
    await expect(channelCheckbox).toHaveAttribute('aria-checked', 'false');
  },
};

/**
 * Figma 716의 60% 슬롯. 좌 280은 유지되고 우측 이름 열만 줄어야 한다.
 * 데이터 기간 드롭다운(min 36)과 체크박스는 눌리지 않는다.
 */
export const Narrow: Story = {
  render: () => (
    <div className="bg-fill-normal-normal w-108 p-3">
      <ChannelTalkEmbeddingTargetPicker
        channels={[makeChannel(1, 2)]}
        activeChannelId="ch-1"
        selectedDocumentIds={['ch-1-doc-0']}
        dataRangeOptions={DATA_RANGE_OPTIONS}
        onActiveChannelChange={() => {}}
        onToggleChannel={() => {}}
        onToggleDocument={() => {}}
        onChannelDataRangeChange={() => {}}
        onDocumentDataRangeChange={() => {}}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const slot = canvasElement.querySelector('div') as HTMLElement;

    // 가로 넘침 없음
    await expect(slot.scrollWidth).toBeLessThanOrEqual(slot.clientWidth + 1);

    // 좌 패널은 280 그대로
    const left = canvas.getByText('채널명').closest('div')?.parentElement as HTMLElement;
    await expect(left.getBoundingClientRect().width).toBe(280);

    // 이름이 잘려서 표시된다
    const name = canvas.getAllByText(/^도큐먼트 스페이스명/)[0];
    await expect(name.scrollWidth).toBeGreaterThan(name.clientWidth);
  },
};
