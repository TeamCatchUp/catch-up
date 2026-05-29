import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';
import { SourceDropdownOpenPreview } from './documentSearchFilterRowPreviews';

export const documentSearchFilterRowSourceDropdownOpenFigmaCase: FigmaLabCase = {
  id: 'document-search-filter-row-source-dropdown-open',
  groupId: 'shared-query-filter',
  owner: 'shared',
  component: 'DocumentSearchFilterRow',
  state: 'source-dropdown-open',
  usedBy: ['home-docs', 'hybrid-search'],
  kind: 'component',
  title: 'DocumentSearchFilterRow / Source Dropdown Open',
  description: 'tool_filter dropdown과 selected chip/input/empty state를 자동 open 상태로 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-63919&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14308:63919',
  },
  viewport: {
    width: 780,
    height: 460,
  },
  data: {
    source: 'fixture',
    fixtures: ['documentSearchFilterRowFixture.sourceDropdownOpen'],
    states: [
      {
        state: 'openEmpty',
        fixture: 'documentSearchFilterRowFixture.sourceDropdownOpen',
        expected: '모든 source가 chip으로 선택된 상태에서 dropdown이 열리고 빈 결과 문구가 중앙에 표시됩니다.',
      },
    ],
  },
  states: ['openEmpty'],
  reuse: [
    {
      figmaPart: 'tool_filter dropdown',
      checked: 'src/shared/components/query/filter/SourceFilterDropdown.tsx',
      decision: 'reuse',
      reason: '선택 chip, delete_circle icon, input 검색, option list empty state를 production dropdown으로 검증합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Dropdown surface',
      code: 'bg-fill-normal border-edge-strong shadow dropdown token',
      decision: 'project-token',
    },
    {
      figma: 'Chip height',
      value: '37px',
      code: 'h-[37px]',
      decision: 'matched',
    },
  ],
  render: () => <SourceDropdownOpenPreview />,
};
