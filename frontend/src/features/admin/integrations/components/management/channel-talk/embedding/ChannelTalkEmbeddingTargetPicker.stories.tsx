import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../../.storybook/catchupStoryParameters';
import { DEFAULT_PERIOD, type Period } from '../../../../constants/period';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';
import ChannelTalkEmbeddingTargetPicker from './ChannelTalkEmbeddingTargetPicker';

const makeChannel = (index: number, documentCount: number): ChannelTalkChannelTarget => ({
  id: `ch-${index}`,
  name: `채널명 text text text text text text ${index}`,
  dataRange: '1개월',
  documentSpaces: Array.from({ length: documentCount }, (_, i) => ({
    id: `ch-${index}-doc-${i}`,
    name: `도큐먼트 스페이스명 text text text ${i}`,
    dataRange: DEFAULT_PERIOD,
  })),
});

// 도큐먼트 수를 3으로 두면 좌 패널의 "전체 3개"(채널 수)와 문구가 겹친다
const CHANNELS: readonly ChannelTalkChannelTarget[] = [makeChannel(1, 8), makeChannel(2, 4), makeChannel(3, 5)];

/** 선택 상태를 들고 있는 스토리 전용 래퍼 — 컴포넌트는 상태를 갖지 않는다 */
function PickerHarness({
  channels = CHANNELS,
  initialVisible,
}: {
  channels?: readonly ChannelTalkChannelTarget[];
  initialVisible?: readonly string[];
}) {
  const [visibleIds, setVisibleIds] = useState<ReadonlySet<string>>(
    new Set(initialVisible ?? channels.map((channel) => channel.id)),
  );
  const [selectedChannelIds, setSelectedChannelIds] = useState<ReadonlySet<string>>(new Set());
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<ReadonlySet<string>>(new Set());
  const [ranges, setRanges] = useState<Record<string, Period>>({});

  const withRange = channels.map((channel) => ({
    ...channel,
    dataRange: ranges[channel.id] ?? channel.dataRange,
    documentSpaces: channel.documentSpaces.map((doc) => ({ ...doc, dataRange: ranges[doc.id] ?? doc.dataRange })),
  }));

  const toggle = (set: ReadonlySet<string>, id: string): ReadonlySet<string> => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  };

  // 표시 해제 시 그 채널의 임베딩 선택도 함께 해제 — 구 모달 시맨틱
  const toggleVisibility = (channelId: string) => {
    const channel = channels.find((item) => item.id === channelId);
    if (!channel) return;
    if (visibleIds.has(channelId)) {
      setSelectedChannelIds((prev) => {
        const next = new Set(prev);
        next.delete(channelId);
        return next;
      });
      setSelectedDocumentIds((prev) => {
        const next = new Set(prev);
        channel.documentSpaces.forEach((doc) => next.delete(doc.id));
        return next;
      });
    }
    setVisibleIds((prev) => toggle(prev, channelId));
  };

  return (
    // Figma 폼 컨테이너 780, 좌우 여백 32 → 선택기는 정확히 716
    <div className="bg-fill-normal-normal w-195 p-8">
      <ChannelTalkEmbeddingTargetPicker
        channels={withRange}
        visibleChannelIds={visibleIds}
        selectedChannelIds={selectedChannelIds}
        selectedDocumentIds={selectedDocumentIds}
        onToggleVisibility={toggleVisibility}
        onToggleChannel={(channelId) => setSelectedChannelIds((prev) => toggle(prev, channelId))}
        onToggleDocument={(_channelId, documentId) => setSelectedDocumentIds((prev) => toggle(prev, documentId))}
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
      states: ['default', 'visibility-toggle', 'nothing-visible', 'narrow'],
      layoutNotes: [
        '716×634 = 좌 채널 목록 280 + 우 선택 상세 436. 좌만 고정, 우가 남은 폭을 먹는다.',
        '컬럼 헤더 pl 12 / pr 20 / py 8, gap 32. 좌측 36 스페이서가 체크박스 자리를 비운다.',
        '채널 헤더 67: fill/normal/strong 배경 + line/normal/assistive 아래선. 도큐먼트 행 56.',
        '바깥 테두리·radius는 스크린샷에서 읽었다 — 노드 속성 미확인.',
      ],
      dataNotes: [
        '원래 ChannelTalkEmbeddingModal 이었는데 커넥터 상세 화면 안으로 들어왔다.',
        '선택 시맨틱은 구 모달 승계 — 좌측은 표시 토글(해제 시 임베딩 선택도 해제), 채널 체크박스는 채널 대화 자체, 집계는 1+스페이스.',
        '기간은 constants/period.ts 의 PERIOD_OPTIONS(1개월~3년·전체), 기본 전체.',
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

    // 채널 대화 1 + 스페이스 8 = 전체 9개
    await expect(canvas.getByText('전체 9개')).toBeInTheDocument();

    // 채널 체크박스는 채널 자신만 고른다 — 하위 전체선택이 아니다
    const channelCheckbox = canvas.getAllByRole('checkbox')[0];
    await userEvent.click(channelCheckbox);
    await expect(channelCheckbox).toHaveAttribute('aria-checked', 'true');
    await expect(canvas.getByText('1개 선택됨')).toBeInTheDocument();

    // 도큐먼트 하나 더 켜면 2
    await userEvent.click(canvas.getAllByRole('checkbox')[1]);
    await expect(canvas.getByText('2개 선택됨')).toBeInTheDocument();
  },
};

/** 좌측 토글은 표시 여부다. 끄면 우측에서 사라지고 그 채널의 선택도 풀린다 */
export const VisibilityToggle: Story = {
  render: () => <PickerHarness />,
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    // 첫 채널의 도큐먼트 하나를 골라둔다
    await userEvent.click(canvas.getAllByRole('checkbox')[1]);
    await expect(canvas.getByText('1개 선택됨')).toBeInTheDocument();

    // 좌측에서 그 채널을 끄면 우측 그룹이 사라진다
    const firstToggle = canvas.getAllByRole('button', { name: /표시/ })[0];
    await userEvent.click(firstToggle);
    await expect(firstToggle).toHaveAttribute('aria-pressed', 'false');
    await expect(canvas.getAllByRole('checkbox')).toHaveLength(11); // 채널 2 + 도큐먼트 4+5

    // 다시 켜면 돌아오지만 선택은 풀려 있다
    await userEvent.click(firstToggle);
    await expect(canvas.queryByText('1개 선택됨')).not.toBeInTheDocument();
  },
};

/** 표시 채널 0개 — 우측 pane에 안내가 나온다 (구 모달 ChannelGroupListEmpty 승계) */
export const NothingVisible: Story = {
  render: () => <PickerHarness initialVisible={[]} />,
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('채널을 선택하세요')).toBeInTheDocument();
    await expect(canvas.getByText(/왼쪽에서 채널을 선택하면/)).toBeInTheDocument();

    // 좌측에서 채널을 켜면 안내가 사라지고 그룹이 나타난다
    await userEvent.click(canvas.getAllByRole('button', { name: /표시/ })[0]);
    await expect(canvas.queryByText('채널을 선택하세요')).not.toBeInTheDocument();
    await expect(canvas.getByText('전체 9개')).toBeInTheDocument();
  },
};

/**
 * Figma 716의 60% 슬롯. 좌 280은 유지되고 우측 이름 열만 줄어야 한다.
 * 기간 드롭다운과 체크박스는 눌리지 않는다.
 */
export const Narrow: Story = {
  render: () => (
    <div className="bg-fill-normal-normal w-108 p-3">
      <ChannelTalkEmbeddingTargetPicker
        channels={[makeChannel(1, 2)]}
        visibleChannelIds={new Set(['ch-1'])}
        selectedChannelIds={new Set()}
        selectedDocumentIds={new Set(['ch-1-doc-0'])}
        onToggleVisibility={() => {}}
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
