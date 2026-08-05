import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { UserMappingRow } from '../../types/userMappingModel';
import UserMappingTable from './UserMappingTable';

const account = (name: string) => ({ name, identifier: 'dlkjfcccldjl@gmail.comcomcomcom' });

const ROWS: readonly UserMappingRow[] = [
  {
    id: 'u1',
    user: { name: '직원20' },
    fullyMapped: true,
    accounts: {
      atlassian: account('직원20'),
      github: account('직원20'),
      slack: account('직원20'),
      channel_talk: account('직원20'),
    },
  },
  {
    id: 'u2',
    user: { name: '직원20' },
    fullyMapped: false,
    accounts: { atlassian: 'unused', github: 'unused', slack: 'unused', channel_talk: 'unused' },
  },
  {
    id: 'u3',
    user: { name: '아주 긴 이름의 사용자입니다 직원20' },
    // 채널톡은 매니저 기반이라 미사용이 감점되지 않는다 — 나머지 3열이 계정이면 녹색
    fullyMapped: true,
    accounts: { atlassian: account('직원20'), github: account('직원20'), slack: account('직원20'), channel_talk: 'unused' },
  },
  {
    id: 'u4',
    user: { name: '직원20' },
    fullyMapped: false,
    accounts: { atlassian: account('직원20') },
  },
];

const meta = {
  title: 'Compositions/Admin/Integrations/User Mapping/UserMappingTable',
  component: UserMappingTable,
  tags: ['autodocs'],
  args: { rows: ROWS },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17060-75363',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17060:75363',
      },
      viewport: { width: 1100, height: 640 },
      states: ['full', 'connector-filtered', 'loading', 'narrow'],
      layoutNotes: [
        '1040 = 24 | 점 8 | 16 | 사용자(≤140) | 16 | 커넥터 1fr×4(셀 ≤165) | 24. 행 py 12 → 66.',
        '커넥터 필터 시 사용자·커넥터 균등 1fr 2열 — 템플릿 상수 교체(userMappingTableGrid.ts).',
        '높이는 박지 않는다 — 66은 py 12 + 2줄 셀 42의 결과.',
      ],
      dataNotes: [
        '셀 3종: 계정(아바타+이름/이메일) / 미사용 태그 / 미연동 "-".',
        '미사용은 응답에 없어 status counts로 추론한다(mapUserMappingRows). 채널톡 미매핑은 항상 미사용이고 점 감점 없음.',
        '빈 상태 배너는 MappingSyncNotice 담당 — 이 표는 rows가 비면 헤더만 남긴다.',
        '스켈레톤은 구 UsersTable 승계(감사 A-5).',
      ],
    }),
  },
} satisfies Meta<typeof UserMappingTable>;

export default meta;

type Story = StoryObj<typeof UserMappingTable>;

const Frame = ({ children, className = 'w-260' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-fill-normal-normal p-4 ${className}`}>{children}</div>
);

export const Full: Story = {
  render: (args) => (
    <Frame>
      <UserMappingTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('Keycloak 사용자')).toBeInTheDocument();
    // 헤더 1 + 본문 4
    await expect(canvas.getAllByRole('row')).toHaveLength(5);
    // 커넥터 4열 헤더
    for (const label of ['Atlassian', 'Github', 'Slack', '채널톡']) {
      await expect(canvas.getByText(label)).toBeInTheDocument();
    }
    // 미사용 태그 행
    await expect(canvas.getAllByText('미사용').length).toBeGreaterThan(0);
    // 상태 점 — 전체 연동 2명(채널톡 미사용은 감점 없음), 일부 미연동 2명
    await expect(canvas.getAllByText('전체 연동됨')).toHaveLength(2);
    await expect(canvas.getAllByText('일부 미연동')).toHaveLength(2);
  },
};

/** 통계 카드 탭 연동 — 커넥터 1열로 재구성 (Figma 17379:78332) */
export const ConnectorFiltered: Story = {
  args: { filterSource: 'channel_talk' },
  render: (args) => (
    <Frame>
      <UserMappingTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('채널톡')).toBeInTheDocument();
    await expect(canvas.queryByText('Atlassian')).not.toBeInTheDocument();
    // 헤더 셀 2 + 점 자리 = 열 3
    const headerCells = canvas.getAllByRole('columnheader');
    await expect(headerCells).toHaveLength(3);
  },
};

export const Loading: Story = {
  args: { rows: [], isLoading: true, skeletonCount: 4 },
  render: (args) => (
    <Frame>
      <UserMappingTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getAllByRole('row')).toHaveLength(5); // 헤더 1 + 스켈레톤 4
  },
};

/** 좁은 슬롯 — 셀이 truncate 되고 하한 아래에서만 가로 스크롤 */
export const Narrow: Story = {
  args: { rows: ROWS.slice(0, 2) },
  render: (args) => (
    <Frame className="w-160">
      <UserMappingTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const table = canvas.getByRole('table');
    const scroller = table.parentElement as HTMLElement;

    // 640 슬롯에서는 스크롤 없이 들어온다 (1px 반올림 여유)
    await expect(scroller.scrollWidth).toBeLessThanOrEqual(scroller.clientWidth + 1);

    // 이메일이 잘려서 표시된다
    const email = canvas.getAllByText(/dlkjfcccldjl/)[0];
    await expect(email.scrollWidth).toBeGreaterThan(email.clientWidth);
  },
};
