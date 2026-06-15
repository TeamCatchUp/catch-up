import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';
import { ResultExpandedFilterRowPreview } from './documentSearchFilterRowPreviews';

export const documentSearchFilterRowResultExpandedFigmaCase: FigmaLabCase = {
  id: 'document-search-filter-row-result-expanded',
  groupId: 'shared-query-filter',
  owner: 'shared',
  component: 'DocumentSearchFilterRow',
  state: 'result-expanded-selected',
  usedBy: ['hybrid-search'],
  kind: 'component',
  title: 'DocumentSearchFilterRow / Result Expanded',
  description: '결과 페이지 expanded panel 안의 tool/date/smart filter row 폭과 tone을 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14314-67307&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14314:67307',
  },
  viewport: {
    width: 940,
    height: 120,
  },
  data: {
    source: 'fixture',
    fixtures: ['documentSearchFilterRowFixture.resultExpanded'],
    states: [
      {
        state: 'selected',
        fixture: 'documentSearchFilterRowFixture.resultExpanded',
        expected: 'expanded panel 내부에서 좌측 filter group과 smart filter control이 20px gap을 유지합니다.',
      },
    ],
  },
  states: ['selected'],
  reuse: [
    {
      figmaPart: 'expanded filter row',
      checked: 'src/shared/components/query/filter/DocumentSearchFilterRow.tsx',
      decision: 'extend',
      reason: 'entry row의 공통 subcomponent를 유지하고 variant로 result-expanded 폭만 조정합니다.',
    },
  ],
  tokens: [
    {
      figma: 'expanded row horizontal gap',
      value: '20px',
      code: 'gap-5',
      decision: 'scale-mapped',
    },
    {
      figma: 'Fill/Normal/Strong',
      code: 'bg-fill-normal-strong',
      decision: 'project-token',
    },
  ],
  render: () => <ResultExpandedFilterRowPreview />,
};
