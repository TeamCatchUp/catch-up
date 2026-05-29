import type { FigmaLabCase } from '@/app/(dev)/figma-lab/_registry/types';
import { SmartFilterStatusPill } from '@/shared/components/query/filter/DocumentSearchFilterRow';

import { DESIGN_SYSTEM_FILE_KEY } from './caseConstants';

function SmartFilterStatusPillPreview() {
  return (
    <div className="bg-fill-normal flex min-h-full items-center gap-5 p-6">
      <SmartFilterStatusPill enabled />
      <SmartFilterStatusPill enabled={false} onApplyClick={() => undefined} />
    </div>
  );
}

export const smartFilterStatusPillFigmaCase: FigmaLabCase = {
  id: 'smart-filter-status-pill',
  groupId: 'shared-query-filter',
  owner: 'shared',
  component: 'SmartFilterStatusPill',
  state: 'applied-basic',
  usedBy: ['hybrid-search'],
  kind: 'component',
  title: 'SmartFilterStatusPill',
  description: '결과 검색바 오른쪽 URL 기준 smart filter status pill의 applied/basic 상태를 확인합니다.',
  figma: {
    url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14308-63671&m=dev',
    fileKey: DESIGN_SYSTEM_FILE_KEY,
    nodeId: '14308:63671',
  },
  viewport: {
    width: 520,
    height: 104,
  },
  data: {
    source: 'fixture',
    fixtures: ['enabled=true', 'enabled=false'],
    states: [
      {
        state: 'applied',
        fixture: 'enabled=true',
        expected: '스마트 필터 적용됨 pill만 표시됩니다.',
      },
      {
        state: 'basic',
        fixture: 'enabled=false',
        expected: '기본 검색 결과 문구와 스마트 필터 적용하기 text button이 함께 표시됩니다.',
      },
    ],
  },
  states: ['applied', 'basic'],
  reuse: [
    {
      figmaPart: 'apply action',
      checked: 'src/shared/components/ui/button.tsx',
      decision: 'reuse',
      reason: '기본 상태 pill 안의 action은 Button text-primary-blue variant를 사용합니다.',
    },
    {
      figmaPart: 'status icon',
      checked: 'public/icons/icon/info_filled.svg',
      decision: 'reuse',
      reason: 'Figma Icon/Normal/Neutral filled icon과 동일 asset을 사용합니다.',
    },
  ],
  tokens: [
    {
      figma: 'Fill/Normal/Strong',
      code: 'bg-fill-strong',
      decision: 'project-token',
    },
    {
      figma: 'Icon/Normal/Neutral',
      code: 'text-icon-neutral',
      decision: 'project-token',
    },
  ],
  render: () => <SmartFilterStatusPillPreview />,
};
