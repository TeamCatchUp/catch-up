import { createRef } from 'react';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';

import { TEMPLATE_ICONS, tipData } from '../constants/questionTips';
import HomeComposer from './HomeComposer';
import QuickTemplateList from './QuickTemplateList';

// Lexical 에디터는 이 테스트의 관심사가 아니다 — 템플릿 모드로 갈아탔는지만 본다.
vi.mock('@/shared/components/query/TemplateInput', () => ({
  default: ({ tip }: { tip: { chipLabel: string } }) => <div data-testid="template-input">{tip.chipLabel}</div>,
}));

const baseInput = (overrides: Partial<UseSearchInputReturn> = {}): UseSearchInputReturn =>
  ({
    value: '',
    setValue: vi.fn(),
    hasText: false,
    isMultiLine: false,
    isFocused: false,
    setIsFocused: vi.fn(),
    isFromTemplate: false,
    setIsFromTemplate: vi.fn(),
    selectedTipIndex: null,
    setSelectedTipIndex: vi.fn(),
    templateFieldValues: {},
    setTemplateFieldValue: vi.fn(),
    templateFieldErrors: {},
    setTemplateFieldErrors: vi.fn(),
    resetTemplateFields: vi.fn(),
    handleSubmit: vi.fn(),
    ...overrides,
  }) as UseSearchInputReturn;

const filters = {
  openPopover: null,
  setOpenPopover: vi.fn(),
  selectedSources: [],
  setSelectedSources: vi.fn(),
  selectedPeople: [],
  togglePerson: vi.fn(),
  selectedDepts: [],
  toggleDept: vi.fn(),
  selectedProjects: [],
  toggleProject: vi.fn(),
  labels: { person: '담당자', dept: '부서명', project: '프로젝트' },
} as unknown as UseSearchFiltersReturn;

const renderComposer = (props: Partial<React.ComponentProps<typeof HomeComposer>> = {}) =>
  render(
    <HomeComposer
      mode="ai"
      onModeChange={vi.fn()}
      input={baseInput()}
      filters={filters}
      inputRef={createRef<HTMLTextAreaElement>()}
      docsSources={[]}
      onDocsSourcesChange={vi.fn()}
      dateRange={undefined}
      onDateRangeChange={vi.fn()}
      smartFilter
      onSmartFilterChange={vi.fn()}
      onAiSubmit={vi.fn()}
      onDocsSubmit={vi.fn()}
      {...props}
    />,
  );

describe('HomeComposer 템플릿', () => {
  it('템플릿을 고르기 전에는 일반 입력창이다', () => {
    renderComposer({ tipData });

    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.queryByTestId('template-input')).not.toBeInTheDocument();
  });

  it('템플릿을 고르면 빈칸 채우기 입력으로 갈아탄다', () => {
    renderComposer({
      tipData,
      input: baseInput({ isFromTemplate: true, selectedTipIndex: 2 }),
    });

    expect(screen.getByTestId('template-input')).toHaveTextContent(tipData[2].chipLabel);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('tipData가 없으면 템플릿 모드로 가지 않는다', () => {
    renderComposer({ input: baseInput({ isFromTemplate: true, selectedTipIndex: 2 }) });

    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('문서 탐색 모드에서는 템플릿 입력을 쓰지 않는다', () => {
    renderComposer({
      mode: 'docs',
      tipData,
      input: baseInput({ isFromTemplate: true, selectedTipIndex: 2 }),
    });

    expect(screen.queryByTestId('template-input')).not.toBeInTheDocument();
  });

  it('템플릿 칩이 목록에서 고른 행과 같은 글리프를 쓴다', () => {
    const index = 3;
    renderComposer({
      tipData,
      input: baseInput({ isFromTemplate: true, selectedTipIndex: index }),
      selectedTemplateLabel: tipData[index].chipLabel,
      TemplateIcon: TEMPLATE_ICONS[index],
    });

    const chipSvg = screen.getByRole('button', { name: '템플릿 해제' }).closest('span')!.querySelector('svg')!;
    expect(chipSvg).toBeInTheDocument();

    // 목록 쪽 같은 인덱스 행의 글리프와 경로가 일치해야 한다.
    const list = render(<QuickTemplateList onTemplateClick={vi.fn()} />);
    const rowSvg = within(list.container).getAllByRole('button')[index].querySelector('svg')!;

    expect(chipSvg.innerHTML).toBe(rowSvg.innerHTML);
  });

  it('템플릿 해제 버튼이 부모에게 알린다', () => {
    const onTemplateRemove = vi.fn();
    renderComposer({
      tipData,
      input: baseInput({ isFromTemplate: true, selectedTipIndex: 0 }),
      selectedTemplateLabel: tipData[0].chipLabel,
      TemplateIcon: TEMPLATE_ICONS[0],
      onTemplateRemove,
    });

    screen.getByRole('button', { name: '템플릿 해제' }).click();
    expect(onTemplateRemove).toHaveBeenCalled();
  });
});
