import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';
import { DatePickerOpenPreview } from './documentSearchFilterRowPreviews';

export const documentSearchFilterRowDatePickerOpenFigmaCase: FigmaLabCase = {
  id: 'document-search-filter-row-date-picker-open',
  groupId: 'shared-query-filter',
  owner: 'shared',
  component: 'DocumentSearchFilterRow',
  state: 'date-picker-open',
  usedBy: ['home-docs', 'hybrid-search'],
  kind: 'component',
  title: 'DocumentSearchFilterRow / Date Picker Open',
  description: 'date_filter trigger와 기존 DateRangePicker overlay 연결을 자동 open 상태로 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14354-63748&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14354:63748',
  },
  viewport: {
    width: 860,
    height: 620,
  },
  data: {
    source: 'fixture',
    fixtures: ['documentSearchFilterRowFixture.datePickerOpen'],
    states: [
      {
        state: 'openSelected',
        fixture: 'documentSearchFilterRowFixture.datePickerOpen',
        expected: '날짜 filter가 selected trigger로 표시되고 DateRangePicker overlay가 열린 상태로 유지됩니다.',
      },
    ],
  },
  states: ['openSelected'],
  reuse: [
    {
      figmaPart: 'date_filter date picker',
      checked: 'src/shared/components/query/filter/DateFilterChip.tsx + src/shared/components/ui/date-range-picker.tsx',
      decision: 'reuse',
      reason: 'trigger 상태와 실제 DateRangePicker overlay를 production 조합으로 검증합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Selected trigger max width',
      value: '180px',
      code: 'max-w-45',
      decision: 'scale-mapped',
    },
    {
      figma: 'Date picker surface',
      code: 'shadow-modal bg-fill-normal-normal',
      decision: 'project-token',
    },
  ],
  render: () => <DatePickerOpenPreview />,
};
