'use client';

import { useRef, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fireEvent, fn, within } from 'storybook/test';

import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';
import type { DocsSource } from '@/shared/types/source';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import HomeComposer from './HomeComposer';
import type { HomeMode } from './ModePicker';

const FIGMA_FILE_KEY = '7UwupbVvmHkElmP2OBJQio';
const figmaUrl = (nodeId: string) =>
  `https://www.figma.com/design/${FIGMA_FILE_KEY}/%F0%9F%8D%85-Design-System?node-id=${nodeId.replace(':', '-')}&m=dev`;

const LONG_PROMPT = [
  '[기능/모듈/에러] 를 지금 가장 빨리 해결할 수 있는 사람을 추천하세요.',
  '먼저 "원 담당자(주요 작업자)"를 찾고, 현재 응답이 어려운 상태(부재/휴가/연락 불가)라면 "대리인"을 1~3명 추천하세요.',
  '추천에는 왜 이 사람인지(최근 작업/리뷰/관련 PR·커밋 근거), 지금 연락 가능한지(슬랙 상태가 보이면 포함), 그리고 바로 확인할 곳을 반드시 포함하세요.',
  '관련 기록이 부족하면 내가 추가로 줄 정보 1가지만 요청하세요.',
].join('\n');

const TEMPLATE_PROMPT =
  '를 지금 가장 빨리 해결할 수 있는 사람을 추천하세요. 먼저 "원 담당자(주요 작업자)"를 찾고, 현재 응답이 어려운 상태라면 대리인을 1~3명 추천하세요.';

interface HomeComposerStoryArgs {
  mode: HomeMode;
  initialValue: string;
  selectedTemplateLabel: string | null;
  docsSources: DocsSource[];
  dateRange: DateRange | undefined;
  smartFilter: boolean;
  onModeChange: (next: HomeMode) => void;
  onAiSubmit: () => void;
  onDocsSubmit: () => void;
  onTemplateRemove: () => void;
  onDocsSourcesChange: (next: DocsSource[]) => void;
  onDateRangeChange: (next: DateRange | undefined) => void;
  onSmartFilterChange: (next: boolean) => void;
}

/** 훅을 부르지 않고 컴포저 props 계약만 만족시키는 스토리 픽스처. */
function useComposerFixture(args: HomeComposerStoryArgs) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [mode, setMode] = useState<HomeMode>(args.mode);
  const [value, setValue] = useState(args.initialValue);
  const [isFocused, setIsFocused] = useState(false);
  const [sources, setSources] = useState<DocsSource[]>([]);
  const [templateLabel, setTemplateLabel] = useState<string | null>(args.selectedTemplateLabel);
  const [docsSources, setDocsSources] = useState<DocsSource[]>(args.docsSources);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(args.dateRange);
  const [smartFilter, setSmartFilter] = useState(args.smartFilter);

  const input = {
    value,
    setValue,
    hasText: value.trim().length > 0,
    isMultiLine: value.includes('\n'),
    isFocused,
    setIsFocused,
    isFromTemplate: templateLabel !== null,
    setIsFromTemplate: fn(),
    selectedTipIndex: null,
    setSelectedTipIndex: fn(),
    templateFieldValues: {},
    setTemplateFieldValue: fn(),
    templateFieldErrors: {},
    setTemplateFieldErrors: fn(),
    resetTemplateFields: fn(),
    handleSubmit: fn(),
  } satisfies UseSearchInputReturn;

  const filters = {
    openPopover: null,
    setOpenPopover: fn(),
    selectedSources: sources,
    setSelectedSources: setSources,
    selectedPeople: [],
    togglePerson: fn(),
    selectedDepts: [],
    toggleDept: fn(),
    selectedProjects: [],
    toggleProject: fn(),
    labels: { person: '담당자', dept: '부서명', project: '프로젝트' },
  } satisfies UseSearchFiltersReturn;

  return {
    inputRef,
    input,
    filters,
    mode,
    onModeChange: (next: HomeMode) => {
      setMode(next);
      args.onModeChange(next);
    },
    templateLabel,
    onTemplateRemove: () => {
      setTemplateLabel(null);
      args.onTemplateRemove();
    },
    docsSources,
    onDocsSourcesChange: (next: DocsSource[]) => {
      setDocsSources(next);
      args.onDocsSourcesChange(next);
    },
    dateRange,
    onDateRangeChange: (next: DateRange | undefined) => {
      setDateRange(next);
      args.onDateRangeChange(next);
    },
    smartFilter,
    onSmartFilterChange: (next: boolean) => {
      setSmartFilter(next);
      args.onSmartFilterChange(next);
    },
  };
}

function HomeComposerCanvas(args: HomeComposerStoryArgs) {
  const state = useComposerFixture(args);

  return (
    <div className="bg-background-normal-normal flex justify-center p-10" style={{ width: 900 }}>
      <HomeComposer
        mode={state.mode}
        onModeChange={state.onModeChange}
        input={state.input}
        filters={state.filters}
        inputRef={state.inputRef}
        docsSources={state.docsSources}
        onDocsSourcesChange={state.onDocsSourcesChange}
        dateRange={state.dateRange}
        onDateRangeChange={state.onDateRangeChange}
        smartFilter={state.smartFilter}
        onSmartFilterChange={state.onSmartFilterChange}
        onAiSubmit={args.onAiSubmit}
        onDocsSubmit={args.onDocsSubmit}
        selectedTemplateLabel={state.templateLabel}
        onTemplateRemove={state.onTemplateRemove}
      />
    </div>
  );
}

function cardOf(canvasElement: HTMLElement) {
  return canvasElement.querySelector('div.w-190') as HTMLElement;
}

const meta = {
  title: 'Compositions/Home/HomeComposer',
  render: (args) => <HomeComposerCanvas {...args} />,
  args: {
    mode: 'ai',
    initialValue: '',
    selectedTemplateLabel: null,
    docsSources: [],
    dateRange: undefined,
    smartFilter: true,
    onModeChange: fn(),
    onAiSubmit: fn(),
    onDocsSubmit: fn(),
    onTemplateRemove: fn(),
    onDocsSourcesChange: fn(),
    onDateRangeChange: fn(),
    onSmartFilterChange: fn(),
  },
  argTypes: {
    mode: { control: 'inline-radio', options: ['ai', 'docs'] },
    initialValue: { control: 'text' },
    selectedTemplateLabel: { control: 'text' },
    smartFilter: { control: 'boolean' },
    docsSources: { control: false },
    dateRange: { control: false },
    onModeChange: { control: false },
    onAiSubmit: { control: false },
    onDocsSubmit: { control: false },
    onTemplateRemove: { control: false },
    onDocsSourcesChange: { control: false },
    onDateRangeChange: { control: false },
    onSmartFilterChange: { control: false },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'home',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: figmaUrl('17496:46058'),
        fileKey: FIGMA_FILE_KEY,
        nodeId: '17496:46058',
      },
      viewport: { width: 900, height: 320 },
      states: ['ai-empty', 'ai-multiline-max', 'ai-template-inserted', 'docs'],
      usedBy: ['home-docs'],
      layoutNotes: [
        '카드 폭 760은 w-190, 라운드 24는 rounded-[24px]로 고정한다.',
        'AI 모드는 입력·컨트롤 사이 gap-8, 하단 행 py-2.5. docs 모드는 gap-6, py-3.',
        '입력 상한 360px은 max-h-90이고, 넘으면 textarea 안에서 스크롤한다.',
      ],
      dataNotes: [
        'ai-empty: 입력 없음, 소스 칩 5개 상시 노출',
        'ai-multiline-max: 상한까지 늘어난 멀티라인 입력',
        'ai-template-inserted: 소스 칩 행 끝에 구분선 + 템플릿 칩',
        'docs: 검색범위/날짜/스마트 필터 행',
      ],
      reuseNotes: [
        'Reuses SourceChipsRow for the AI-mode attached row.',
        'Reuses DocumentSearchFilterRow for the docs-mode attached row.',
        'Reuses the HomeMode type from ModePicker; ModePicker itself is untouched.',
      ],
      interactionNotes: [
        'Mode toggle switches the attached row between source chips and the search filter row.',
        'Enter submits per mode; an active IME composition does not submit.',
        'The left + button renders without behavior — the design defines no click result.',
      ],
      tokenNotes: [
        'Figma Fill/Overlay/Background_Elevated maps to bg-fill-overlay-background-elevated.',
        'Figma Fill/Normal/Assistive maps to bg-fill-normal-assistive.',
        'Figma radius/lg maps to rounded-lg on the mode toggle.',
        'Figma Fill/Normal/interaction/Inactive maps to bg-fill-normal-interaction-inactive.',
      ],
    }),
  },
} satisfies Meta<HomeComposerStoryArgs>;

export default meta;

type Story = StoryObj<HomeComposerStoryArgs>;

/** AI 모드 기본 — 소스 칩 행이 포커스 없이도 상시 노출된다. */
export const AiEmpty: Story = {
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step('카드 기하가 시안 폭과 라운드를 지킨다', async () => {
      const card = cardOf(canvasElement);
      await expect(card.getBoundingClientRect().width).toBe(760);
      await expect(getComputedStyle(card).borderRadius).toBe('24px');
    });

    await step('모드 토글은 AI 선택 · 높이 36', async () => {
      const tablist = canvas.getByRole('tablist', { name: '모드 선택' });
      await expect(tablist.getBoundingClientRect().height).toBe(36);
      await expect(canvas.getByRole('tab', { name: '캐치스턴트 AI' })).toHaveAttribute('aria-selected', 'true');
      await expect(canvas.getByRole('tab', { name: '문서 탐색' })).toHaveAttribute('aria-selected', 'false');
    });

    await step('소스 칩 5개가 하단 행에 붙는다', async () => {
      for (const label of ['Confluence', 'Jira', 'Slack', 'Github', '채널톡']) {
        await expect(canvas.getByRole('button', { name: label })).toBeVisible();
      }
    });

    await step('시안에 없는 요소는 만들지 않는다', async () => {
      await expect(canvas.queryByText('Standard')).toBeNull();
      await expect(canvas.queryByRole('button', { name: '검색 범위 필터' })).toBeNull();
      await expect(canvas.queryByRole('button', { name: '템플릿 해제' })).toBeNull();
    });

    await step('+ 버튼은 렌더되지만 동작이 없다', async () => {
      await expect(canvas.getByRole('button', { name: '추가' })).toBeVisible();
    });
  },
};

/** 모드 토글로 하단 부착 행이 소스 칩 ↔ 검색 필터로 바뀐다. */
export const ModeSwitch: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'home',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: figmaUrl('17481:116165'),
        fileKey: FIGMA_FILE_KEY,
        nodeId: '17481:116165',
      },
      states: ['ai-selected', 'docs-selected'],
    }),
  },
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('시작은 AI — 소스 칩이 보이고 필터 행은 없다', async () => {
      await expect(canvas.getByRole('button', { name: 'Confluence' })).toBeVisible();
      await expect(canvas.queryByRole('button', { name: '검색 범위 필터' })).toBeNull();
    });

    await step('문서 탐색으로 전환하면 하단 행이 필터 행으로 바뀐다', async () => {
      await userEvent.click(canvas.getByRole('tab', { name: '문서 탐색' }));
      await expect(args.onModeChange).toHaveBeenCalledWith('docs');

      await expect(canvas.getByRole('tab', { name: '문서 탐색' })).toHaveAttribute('aria-selected', 'true');
      await expect(canvas.getByRole('button', { name: '검색 범위 필터' })).toBeVisible();
      await expect(canvas.queryByRole('button', { name: 'Confluence' })).toBeNull();
    });

    await step('다시 AI로 돌아오면 소스 칩이 복귀한다', async () => {
      await userEvent.click(canvas.getByRole('tab', { name: '캐치스턴트 AI' }));
      await expect(args.onModeChange).toHaveBeenCalledWith('ai');
      await expect(canvas.getByRole('button', { name: 'Confluence' })).toBeVisible();
      await expect(canvas.queryByRole('button', { name: '검색 범위 필터' })).toBeNull();
    });

    await step('카드 폭은 모드가 바뀌어도 760을 유지한다', async () => {
      await expect(cardOf(canvasElement).getBoundingClientRect().width).toBe(760);
    });
  },
};

/** 멀티라인 확장 — 입력이 시안 상한까지만 늘어난다. */
export const AiMultilineMax: Story = {
  args: { initialValue: LONG_PROMPT },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'home',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: figmaUrl('17510:46437'),
        fileKey: FIGMA_FILE_KEY,
        nodeId: '17510:46437',
      },
      states: ['ai-multiline-max'],
    }),
  },
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step('입력 높이는 상한 360을 넘지 않는다', async () => {
      const textarea = canvas.getByRole('textbox');
      await expect(textarea.getBoundingClientRect().height).toBeLessThanOrEqual(360);
    });

    await step('길어져도 카드 폭과 하단 소스 칩 행은 그대로다', async () => {
      await expect(cardOf(canvasElement).getBoundingClientRect().width).toBe(760);
      await expect(canvas.getByRole('button', { name: 'Confluence' })).toBeVisible();
    });
  },
};

/** 템플릿 삽입 — 소스 칩 행 끝에 구분선과 템플릿 칩이 붙는다. */
export const AiTemplateInserted: Story = {
  args: {
    initialValue: TEMPLATE_PROMPT,
    selectedTemplateLabel: '담당자 & 대리인 찾기',
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'home',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: figmaUrl('17467:42895'),
        fileKey: FIGMA_FILE_KEY,
        nodeId: '17467:42895',
      },
      states: ['ai-template-inserted'],
    }),
  },
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('템플릿 칩이 소스 칩 뒤에 붙는다', async () => {
      const chip = canvas.getByText('담당자 & 대리인 찾기');
      const lastSource = canvas.getByRole('button', { name: '채널톡' });
      await expect(chip.getBoundingClientRect().left).toBeGreaterThan(lastSource.getBoundingClientRect().right);
    });

    await step('칩 높이는 소스 칩과 같은 36', async () => {
      const remove = canvas.getByRole('button', { name: '템플릿 해제' });
      await expect(remove.closest('span')!.getBoundingClientRect().height).toBe(36);
    });

    await step('× 를 누르면 템플릿이 해제된다', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '템플릿 해제' }));
      await expect(args.onTemplateRemove).toHaveBeenCalled();
      await expect(canvas.queryByText('담당자 & 대리인 찾기')).toBeNull();
    });
  },
};

/** 문서 탐색 모드 — 하단 행이 검색범위·날짜·스마트 필터로 바뀐다. */
export const Docs: Story = {
  args: {
    mode: 'docs',
    docsSources: ['slack', 'confluence'],
    dateRange: { from: new Date(2026, 4, 13), to: new Date(2026, 4, 14) },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'home',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: figmaUrl('17481:115866'),
        fileKey: FIGMA_FILE_KEY,
        nodeId: '17481:115866',
      },
      states: ['docs'],
    }),
  },
  play: async ({ args, canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step('필터 행이 하단에 붙고 소스 칩은 사라진다', async () => {
      await expect(canvas.getByRole('button', { name: '검색 범위 필터' })).toBeVisible();
      await expect(canvas.getByRole('button', { name: '날짜 필터' })).toBeVisible();
      await expect(canvas.getByRole('switch', { name: '스마트 필터' })).toBeVisible();
      await expect(canvas.queryByRole('button', { name: 'Confluence' })).toBeNull();
    });

    await step('필터 행은 카드 안에 넘치지 않고 들어간다', async () => {
      const card = cardOf(canvasElement);
      await expect(card.getBoundingClientRect().width).toBe(760);
      await expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth);
    });

    await step('Enter는 docs submit으로 분기하고, IME 조합 중에는 보내지 않는다', async () => {
      const textarea = canvas.getByRole('textbox');

      fireEvent.change(textarea, { target: { value: '지난주 결제 롤백' } });
      fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });
      await expect(args.onDocsSubmit).not.toHaveBeenCalled();

      fireEvent.keyDown(textarea, { key: 'Enter' });
      await expect(args.onDocsSubmit).toHaveBeenCalledTimes(1);
      await expect(args.onAiSubmit).not.toHaveBeenCalled();
    });
  },
};
