import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, userEvent, within } from 'storybook/test';

import IconPersonFilled from '@/public/icons/icon/person_filled.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { REVIEW_QUEUE_ASSIGNEE_OPTIONS, REVIEW_QUEUE_CHANNEL_OPTIONS } from '../../fixtures/llmWikiFixtures';
import ReviewQueueFilterSearchPanel from './ReviewQueueFilterSearchPanel';

/**
 * 선택은 소비처 상태다 — 패널은 props만 받는다.
 * 스토리에서만 그 상태를 들어 토글이 실제로 왕복하는지 본다.
 */
function StatefulPanel({
  options = REVIEW_QUEUE_ASSIGNEE_OPTIONS,
  initialSelectedIds = [],
  placeholder = '담당자 검색',
  OptionIcon = IconPersonFilled,
}: {
  options?: typeof REVIEW_QUEUE_ASSIGNEE_OPTIONS;
  initialSelectedIds?: readonly string[];
  placeholder?: string;
  OptionIcon?: typeof IconPersonFilled;
}) {
  const [selectedIds, setSelectedIds] = useState<readonly string[]>(initialSelectedIds);

  return (
    // 시안 2차 카드(300 · radius 12 · Shadow/Modal)를 슬롯이 재현한다 — 패널은 폭을 갖지 않는다.
    <div className="border-line-normal-normal bg-background-normal-normal shadow-modal w-75 rounded-xl py-2.5">
      <ReviewQueueFilterSearchPanel
        options={options}
        selectedIds={selectedIds}
        onToggle={(optionId) =>
          setSelectedIds((prev) =>
            prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId],
          )
        }
        placeholder={placeholder}
        OptionIcon={OptionIcon}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/LLM Wiki/ReviewQueue/ReviewQueueFilterSearchPanel',
  component: ReviewQueueFilterSearchPanel,
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=18112-47410',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '18112:47410',
      },
      viewport: { width: 360, height: 460 },
      states: ['default', 'search', 'no-results(dev-preview)', 'with-chips', 'clear-all'],
      reuseNotes: [
        'cmdk 래퍼 `shared/components/ui/command`를 쓴다(직접 import 금지). Popover+Command 조합의 선례는 AccountSelectDropdown, 칩+검색창 조합의 선례는 SourceFilterDropdown·FilterOptionList다.',
        'FilterOptionList(shared, 소비처 0)가 같은 DS 조각으로 만들어져 있고 직책 라벨 규격(max-w 72·min-w 30)까지 일치한다. 그대로 쓰지 않은 이유는 셋이다 — ① 선택 키가 name 문자열이라 동명이인에서 깨진다(픽스처에 "이진수" 2명을 둬 이 계약을 밟는다) ② 빈 결과 표시가 없다 ③ 모달 본문용 레이아웃(self-stretch·flex-1)이라 드롭다운 패널과 맞지 않는다. 공유 코드라 고치지 않고 이 화면 몫만 만들었다.',
        'cancel_small·TextfiledDelete·person_filled·wiki_channel 전부 기존 에셋 재사용 — 신규 export 없음.',
      ],
      dataNotes: [
        '옵션·직책은 전부 fixture다(REVIEW_QUEUE_ASSIGNEE_OPTIONS·REVIEW_QUEUE_CHANNEL_OPTIONS). 컴포넌트는 목록을 알지 못한다.',
        '"PM"은 시안 실재 요소이고 코드에서는 trailingLabel optional이다 — 어느 API가 직책을 주는지는 미정(디자이너·백엔드 질문 #30).',
        '선택 개수 상한은 두지 않았다 — 시안이 검색창을 min-h 40 / max-h 150 + 스크롤로 정의해 초과분을 흡수한다. 리포 선례 2곳도 상한이 없다.',
        '"검색 결과가 없습니다."는 이 화면 시안에 없다 — 리포 관례(AccountSelectDropdown·SourceFilterDropdown 동일 문구)를 채택했고 이 상태만 dev-preview로 표기한다.',
      ],
      tokenNotes: [
        '검색창: Fill/Normal/Strong 배경, 포커스 테두리 1.5px Line/Primary/Normal #69A5FF = focus-within:border-line-primary-normal, radius 8, px 12 py 8.',
        '칩: 흰 배경 + Line/Normal/Strong #DBDCDF 테두리, h 37 = h-9.25, radius rounded(full), 라벨 body(md)/small max-w 150 = max-w-37.5.',
        '행: h 40, radius 12 = rounded-xl, 글리프틀 34 = size-8.5(Fill/Normal/Strong + Line/Normal/Neutral 테두리 + p-1.5), 글리프 20.',
        '직책: body(md)/xsmall + Text/Normal/Assistive #B1B8BE, max-w 72 = max-w-18, min-w 30 = min-w-7.5.',
        '카드 그림자는 Shadow/Modal이고 코드 토큰 --shadow-modal(0 6px 25px rgba(0,0,0,0.28))과 값이 정확히 일치한다 — 1차 카드의 Shadow/Dropdown menu와 다른 토큰이다.',
      ],
      layoutNotes: [
        '패널은 폭을 갖지 않는다 — 300은 2차 카드(슬롯)의 값이다. 고정 치수는 검색창 min-h 40·max-h 150, 칩 h 37, 행 h 40, 글리프틀 34, 직책 72/30뿐이고 전부 컨트롤·글리프 크기다.',
        '폭 흡수는 레벨마다 하나다 — 카드 안에서는 검색창 내부 열, 행 안에서는 라벨(min-w-0 flex-1). 칩·글리프·직책은 shrink-0.',
        '축소 순서: 칩 라벨 truncate(150 상한) → 행 라벨 truncate → 칩 줄바꿈(flex-wrap) → 검색창 세로 스크롤(150 상한). 가로 스크롤은 없다.',
      ],
      interactionNotes: [
        'cmdk 자동 필터를 끄고 소문자 includes로 직접 거른다 — 한글 퍼지 매칭이 예측되지 않는다는 에디터 메뉴(slashItems)의 판정을 따랐다.',
        '선택된 항목은 목록에서 빠지고 칩으로 옮겨간다(SourceFilterDropdown·FilterOptionList 선례 동일).',
        '검색창은 열릴 때 포커스를 받는다 — 시안이 Bars_large를 state=focused로 그려 둔 근거다.',
        '초기화 버튼은 검색어와 선택을 함께 비운다(리포 선례 동일). 검색어·선택이 모두 없으면 렌더되지 않는다.',
      ],
    }),
  },
} satisfies Meta<typeof ReviewQueueFilterSearchPanel>;

export default meta;
type Story = StoryObj<typeof ReviewQueueFilterSearchPanel>;

/** 기본 목록. 직책이 있는 행과 없는 행이 함께 있다. */
export const Default: Story = {
  render: () => <StatefulPanel />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByPlaceholderText('담당자 검색')).toBeInTheDocument();
    await expect(canvas.getAllByRole('option')).toHaveLength(REVIEW_QUEUE_ASSIGNEE_OPTIONS.length);

    // 행 기하 — 높이 40, 글리프틀 34.
    const row = canvas.getByText('직원10').closest('[role=option]') as HTMLElement;
    await expect(row.getBoundingClientRect().height).toBe(40);
    await expect((row.firstElementChild as HTMLElement).getBoundingClientRect().width).toBe(34);

    // 직책은 있는 행에만 붙는다.
    await expect(within(row).getByText('PM')).toBeInTheDocument();
    const externalRow = canvas.getByText('외부 협력자').closest('[role=option]') as HTMLElement;
    await expect(within(externalRow).queryByText('PM')).toBeNull();

    // 검색어·선택이 없으면 초기화 버튼이 없다.
    await expect(canvas.queryByRole('button', { name: '담당자 검색 초기화' })).toBeNull();
  },
};

/** 검색어 입력. cmdk 자동 필터가 아니라 includes가 거른 결과다. */
export const Search: Story = {
  render: () => <StatefulPanel />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.type(canvas.getByPlaceholderText('담당자 검색'), '이진수');

    // 동명이인 2명이 함께 남는다 — 이름이 아니라 id가 선택 키라는 계약의 전제다.
    await expect(canvas.getAllByText('이진수')).toHaveLength(2);
    await expect(canvas.queryByText('직원10')).toBeNull();
    await expect(canvas.getAllByRole('option')).toHaveLength(2);
  },
};

/** 검색 결과 0건. 이 문구는 시안이 아니라 리포 관례를 따른 것이다(dev-preview). */
export const NoResults: Story = {
  render: () => <StatefulPanel />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.type(canvas.getByPlaceholderText('담당자 검색'), '존재하지않는이름');

    await expect(await canvas.findByText('검색 결과가 없습니다.')).toBeInTheDocument();
    await expect(canvas.queryAllByRole('option')).toHaveLength(0);
  },
};

/** 선택 → 칩. 동명이인 중 한 명만 골라도 나머지는 목록에 남아야 한다. */
export const SelectToChip: Story = {
  render: () => <StatefulPanel />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const optionsBefore = canvas.getAllByRole('option').length;
    await userEvent.click(canvas.getAllByText('이진수')[0]);

    // 고른 행만 목록에서 빠진다 — 이름으로 걸렀다면 동명이인까지 함께 사라진다.
    await expect(canvas.getAllByRole('option')).toHaveLength(optionsBefore - 1);
    await expect(canvas.getAllByText('이진수')).toHaveLength(2); // 칩 1 + 남은 행 1

    // 칩에는 해제 버튼이 달린다.
    const removeButton = canvas.getByRole('button', { name: '이진수 선택 해제' });
    await userEvent.click(removeButton);
    await expect(canvas.getAllByRole('option')).toHaveLength(optionsBefore);
  },
};

/** 칩이 쌓인 상태. 검색창이 자라되 150에서 멈추고 안에서 스크롤한다 — 선택 상한은 없다. */
export const ManyChips: Story = {
  render: () => (
    <StatefulPanel initialSelectedIds={REVIEW_QUEUE_ASSIGNEE_OPTIONS.slice(0, 6).map((option) => option.id)} />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    const chips = canvas.getAllByRole('button', { name: /선택 해제$/ });
    await expect(chips).toHaveLength(6);

    // 칩 6개가 들어가도 검색창은 150을 넘지 않고, 넘친 만큼은 스크롤로 흡수한다.
    const searchBox = canvas.getByPlaceholderText('담당자 검색').closest('[role=presentation]') as HTMLElement;
    const boxHeight = searchBox.getBoundingClientRect().height;
    await expect(boxHeight).toBeGreaterThan(40);
    await expect(boxHeight).toBeLessThanOrEqual(150);

    const scroller = searchBox.firstElementChild as HTMLElement;
    await expect(scroller.scrollHeight).toBeGreaterThan(scroller.clientHeight);

    // 선택된 6명은 목록에서 빠져 있다.
    await expect(canvas.getAllByRole('option')).toHaveLength(REVIEW_QUEUE_ASSIGNEE_OPTIONS.length - 6);
  },
};

/** 초기화. 검색어와 선택을 함께 비운다. */
export const ClearAll: Story = {
  render: () => <StatefulPanel initialSelectedIds={['u-seoyeon', 'u-jinsu']} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.type(canvas.getByPlaceholderText('담당자 검색'), '정');
    await userEvent.click(canvas.getByRole('button', { name: '담당자 검색 초기화' }));

    await expect(canvas.getByPlaceholderText('담당자 검색')).toHaveValue('');
    await expect(canvas.queryAllByRole('button', { name: /선택 해제$/ })).toHaveLength(0);
    await expect(canvas.getAllByRole('option')).toHaveLength(REVIEW_QUEUE_ASSIGNEE_OPTIONS.length);
  },
};

/** 대상 채널 축. 같은 패널에 글리프와 픽스처만 바뀐다 — 직책 자리는 비어 있다. */
export const ChannelAxis: Story = {
  render: () => (
    <StatefulPanel options={REVIEW_QUEUE_CHANNEL_OPTIONS} placeholder="부서명 검색" OptionIcon={IconWikiChannel} />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getAllByRole('option')).toHaveLength(REVIEW_QUEUE_CHANNEL_OPTIONS.length);
    await expect(canvas.getByPlaceholderText('부서명 검색')).toBeInTheDocument();

    // 채널 행은 직책 라벨이 없다 — 행 자식은 글리프틀과 라벨 둘뿐이다.
    const row = canvas.getByText('결제').closest('[role=option]') as HTMLElement;
    await expect(row.children).toHaveLength(2);
  },
};
