import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';
import { ResultSearchBarCollapsedPreview, ResultSearchBarExpandedPreview } from './resultSearchBarPreviews';

export const resultSearchBarCollapsedFigmaCase: FigmaLabCase = {
  id: 'result-search-bar-collapsed',
  groupId: 'hybrid-search',
  owner: 'feature',
  component: 'ResultSearchBar',
  state: 'collapsed-applied',
  kind: 'section',
  title: 'ResultSearchBar / Collapsed',
  description: '결과 페이지 collapsed search bar와 smart filter status pill 조립을 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-63671&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14308:63671',
  },
  viewport: {
    width: 1240,
    height: 160,
  },
  layout: {
    shell: 'Result page header search area',
    container: '900px fixed search bar plus URL-based smart filter status pill',
    stack: 'Search input/action group -> SmartFilterStatusPill',
    responsive: ['desktop Figma frame 기준 case입니다'],
    relationships: [
      {
        from: 'ResultSearchBar',
        to: 'SmartFilterStatusPill',
        figma: '20px horizontal gap',
        code: 'gap-5',
        note: 'expanded 여부와 관계없이 오른쪽 status pill은 유지됩니다.',
      },
      {
        from: 'Cancel action',
        to: 'Send action',
        figma: '10px action row gap with 24px divider',
        code: 'gap-2.5 and h-6 divider',
      },
    ],
  },
  data: {
    source: 'fixture',
    fixtures: ['resultSearchBarFixture.appliedCollapsed'],
    states: [
      {
        state: 'collapsedApplied',
        fixture: 'resultSearchBarFixture.appliedCollapsed',
        expected: '검색어가 있는 collapsed bar 오른쪽에 스마트 필터 적용됨 pill이 20px gap으로 표시됩니다.',
      },
    ],
  },
  states: ['collapsedApplied'],
  reuse: [
    {
      figmaPart: 'search bar actions',
      checked: 'src/features/hybrid-search/components/search-bar/ResultSearchBar.tsx',
      decision: 'feature-local',
      reason: '결과 페이지 expanded/collapsed 상태와 URL commit 동작을 갖는 feature-local 조립 컴포넌트입니다.',
    },
    {
      figmaPart: 'smart filter status',
      checked: 'src/shared/components/query/filter/SmartFilterStatusPill.tsx',
      decision: 'reuse',
      reason: 'collapsed와 expanded 상태 모두에서 동일한 URL 기준 status pill을 사용합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Search bar width',
      value: '900px',
      code: 'w-225',
      decision: 'scale-mapped',
    },
    {
      figma: 'search/status gap',
      value: '20px',
      code: 'gap-5',
      decision: 'scale-mapped',
    },
    {
      figma: 'Divider height',
      value: '24px',
      code: 'h-6',
      decision: 'scale-mapped',
    },
  ],
  render: () => <ResultSearchBarCollapsedPreview />,
};

export const resultSearchBarExpandedFigmaCase: FigmaLabCase = {
  id: 'result-search-bar-expanded',
  groupId: 'hybrid-search',
  owner: 'feature',
  component: 'ResultSearchBar',
  state: 'expanded-draft',
  kind: 'section',
  title: 'ResultSearchBar / Expanded',
  description: '결과 페이지 expanded search box와 내부 filter row 조립을 자동 expanded 상태로 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-61606&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14308:61606',
  },
  viewport: {
    width: 1240,
    height: 760,
  },
  layout: {
    shell: 'Result page header expanded search area',
    container: '900px fixed expanded search box plus URL-based smart filter status pill',
    stack: 'Search input/action row -> divider -> expanded filter/history/promo panel',
    responsive: ['desktop Figma frame 기준 case입니다'],
    relationships: [
      {
        from: 'ResultSearchBar',
        to: 'SmartFilterStatusPill',
        figma: '20px horizontal gap',
        code: 'gap-5',
        note: 'expanded 상태에서도 오른쪽 status pill은 사라지지 않습니다.',
      },
      {
        from: 'Action row',
        to: 'Expanded divider',
        figma: '10px action gap and full-width divider',
        code: 'gap-2.5 and bg-line-normal-neutral h-px',
      },
      {
        from: 'Expanded panel',
        to: 'DocumentSearchFilterRow',
        figma: 'filter row enters panel body',
        code: 'ResultSearchBarExpandedPanel -> DocumentSearchFilterRow variant result-expanded',
      },
    ],
  },
  data: {
    source: 'fixture',
    fixtures: ['resultSearchBarFixture.expandedDraft'],
    states: [
      {
        state: 'expandedDraft',
        fixture: 'resultSearchBarFixture.expandedDraft',
        expected: 'input focus 없이도 lab route 진입 후 expanded panel과 내부 draft smart filter row가 표시됩니다.',
      },
    ],
  },
  states: ['expandedDraft'],
  reuse: [
    {
      figmaPart: 'expanded search box',
      checked: 'src/features/hybrid-search/components/search-bar/ResultSearchBar.tsx',
      decision: 'feature-local',
      reason: 'expanded/collapsed state machine과 action row를 production component로 검증합니다.',
    },
    {
      figmaPart: 'expanded filter row',
      checked: 'src/features/hybrid-search/components/search-bar/ResultSearchBarExpandedPanel.tsx',
      decision: 'reuse',
      reason: 'panel 내부 filter/history/promo 조립을 실제 feature component로 확인합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Expanded search box width',
      value: '900px',
      code: 'w-225',
      decision: 'scale-mapped',
    },
    {
      figma: 'Expanded search box height',
      value: '636px',
      code: 'custom 636px height in ResultSearchBar expanded state',
      decision: 'matched',
    },
    {
      figma: 'search/status gap',
      value: '20px',
      code: 'gap-5',
      decision: 'scale-mapped',
    },
  ],
  render: () => <ResultSearchBarExpandedPreview />,
};
