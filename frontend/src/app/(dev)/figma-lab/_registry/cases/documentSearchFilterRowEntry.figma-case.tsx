import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';
import { EntryFilterRowPreview } from './documentSearchFilterRowPreviews';

export const documentSearchFilterRowEntryFigmaCase: FigmaLabCase = {
  id: 'document-search-filter-row-entry',
  groupId: 'shared-query-filter',
  owner: 'shared',
  component: 'DocumentSearchFilterRow',
  state: 'entry-default-selected',
  usedBy: ['home-docs', 'hybrid-search'],
  kind: 'component',
  title: 'DocumentSearchFilterRow / Entry',
  description: '문서 탐색 진입점의 tool/date/smart filter row를 default와 selected 상태로 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-62155&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14308:62155',
  },
  viewport: {
    width: 780,
    height: 180,
  },
  data: {
    source: 'fixture',
    fixtures: ['documentSearchFilterRowFixture.entryDefault', 'documentSearchFilterRowFixture.entrySelected'],
    states: [
      {
        state: 'default',
        fixture: 'documentSearchFilterRowFixture.entryDefault',
        expected: '검색 범위와 날짜 chip은 기본 폭을 유지하고 smart filter control은 primary-neutral tone으로 표시됩니다.',
      },
      {
        state: 'selected',
        fixture: 'documentSearchFilterRowFixture.entrySelected',
        expected: '선택된 tool/date 값이 chip 안에서 truncation되고 input 검색 overlay는 유지됩니다.',
      },
    ],
  },
  states: ['default', 'selected'],
  reuse: [
    {
      figmaPart: 'tool_filter',
      checked: 'src/shared/components/query/filter/SourceFilterDropdown.tsx',
      decision: 'reuse',
      reason: '공통 source dropdown, chip, 검색 input, icon asset을 그대로 사용합니다.',
    },
    {
      figmaPart: 'date_filter',
      checked: 'src/shared/components/query/filter/DateFilterChip.tsx',
      decision: 'reuse',
      reason: '기존 DateRangePicker 연결과 trigger 상태 표현을 유지합니다.',
    },
    {
      figmaPart: 'smart_filter',
      checked: 'src/shared/components/query/filter/SmartFilterControl.tsx',
      decision: 'reuse',
      reason: 'Tooltip, Switch, info_filled icon을 조합한 공통 control입니다.',
    },
  ],
  tokens: [
    {
      figma: 'gap/20',
      value: '20px',
      code: 'gap-5',
      decision: 'scale-mapped',
    },
    {
      figma: 'gap/10',
      value: '10px',
      code: 'gap-2.5',
      decision: 'scale-mapped',
    },
    {
      figma: 'Fill/Primary/Normal/Neutral',
      code: 'bg-fill-primary-normal-neutral',
      decision: 'project-token',
    },
  ],
  render: () => <EntryFilterRowPreview />,
};
