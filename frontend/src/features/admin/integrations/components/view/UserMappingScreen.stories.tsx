'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { Button } from '@/shared/components/ui/button';
import Pagination from '@/shared/components/ui/pagination';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { CONNECTOR_CONTENT } from '../../constants/connectorContent';
import { CONNECTOR_LOGOS } from '../../constants/connectorLogos';
import type { AccountOverride } from '../../hooks/useUserMappingEdit';
import type { IntegrationService } from '../../types/integrationModel';
import type { MappingSource, UserMappingRow } from '../../types/userMappingModel';
import type { AccountOption } from '../user-mapping/AccountSelectDropdown';
import MappingActionsBar from '../user-mapping/MappingActionsBar';
import MappingFilterChips, { type MappingStatusFilter } from '../user-mapping/MappingFilterChips';
import MappingStatCardRow, { type MappingStatItem } from '../user-mapping/MappingStatCardRow';
import MappingSyncNotice from '../user-mapping/MappingSyncNotice';
import UserMappingTable from '../user-mapping/UserMappingTable';

/*
 * /admin/user-mapping 화면 스토리. UserMappingView와 같은 골격으로 Compositions를
 * 합치되 데이터 훅 대신 fixture를 쓴다 — 화면 조립 규칙(섹션 gap 40, 필터/액션
 * 한 줄, 표 아래 페이지네이션)을 고정하는 것이 목적이다.
 */

interface UserMappingScreenStoryArgs {
  onFilterChange: (next: MappingStatusFilter) => void;
  onPageChange: (page: number) => void;
}

const STAT_ORDER = ['jira', 'github', 'slack', 'confluence', 'channel_talk'] as const;

/** 통계 fixture — mapped/users. 채널톡만 낮게 둬 완료율 차이를 보여준다 */
const STAT_COUNTS: Record<(typeof STAT_ORDER)[number], { users: number; mapped: number }> = {
  jira: { users: 12, mapped: 12 },
  github: { users: 12, mapped: 10 },
  slack: { users: 12, mapped: 11 },
  confluence: { users: 12, mapped: 12 },
  channel_talk: { users: 12, mapped: 4 },
};

const STAT_FIXTURE: MappingStatItem[] = STAT_ORDER.map((key) => {
  const { users, mapped } = STAT_COUNTS[key];
  return {
    key,
    Logo: CONNECTOR_LOGOS[key],
    name: CONNECTOR_CONTENT[key as IntegrationService].name,
    percent: users > 0 ? Math.round((mapped / users) * 100) : 0,
    countLabel: `${mapped}/${users}`,
  };
});

const account = (name: string, identifier: string) => ({ name, identifier });

/** 전체 연동 / 일부 미연동 / 미사용 선언이 골고루 섞인 5행 */
const ROWS_FIXTURE: readonly UserMappingRow[] = [
  {
    id: 'u-1',
    user: { name: '김수현' },
    fullyMapped: true,
    accounts: {
      atlassian: account('김수현', 'user@example.com'),
      github: account('soohyun-kim', 'user@example.com'),
      slack: account('김수현', 'user@example.com'),
      channel_talk: account('김수현', 'user@example.com'),
    },
  },
  {
    id: 'u-2',
    user: { name: '이정원' },
    fullyMapped: false,
    accounts: {
      atlassian: account('이정원', 'user@example.com'),
      github: account('jungwon-lee', 'user@example.com'),
      slack: null,
      channel_talk: null,
    },
  },
  {
    id: 'u-3',
    user: { name: '박민지' },
    fullyMapped: true,
    accounts: {
      atlassian: account('박민지', 'user@example.com'),
      github: 'unused',
      slack: account('박민지', 'user@example.com'),
      channel_talk: account('박민지', 'user@example.com'),
    },
  },
  {
    id: 'u-4',
    user: { name: '최다은' },
    fullyMapped: false,
    accounts: {
      atlassian: null,
      github: account('daeun-choi', 'user@example.com'),
      slack: account('최다은', 'user@example.com'),
      channel_talk: null,
    },
  },
  {
    id: 'u-5',
    user: { name: '직원25' },
    fullyMapped: true,
    accounts: {
      atlassian: account('직원25', 'user@example.com'),
      github: account('haneul-jung', 'user@example.com'),
      slack: account('직원25', 'user@example.com'),
      channel_talk: 'unused',
    },
  },
];

const EDIT_OPTIONS: Partial<Record<MappingSource, AccountOption[]>> = {
  atlassian: [
    { id: 'at-1', name: '김수현', identifier: 'user@example.com' },
    { id: 'at-2', name: '이정원', identifier: 'user@example.com' },
  ],
  github: [
    { id: 'gh-1', name: 'soohyun-kim', identifier: 'user@example.com' },
    { id: 'gh-2', name: 'jungwon-lee', identifier: 'user@example.com' },
  ],
  slack: [{ id: 'sl-1', name: '김수현', identifier: 'user@example.com' }],
  channel_talk: [{ id: 'ct-1', name: '김수현', identifier: 'user@example.com' }],
};

/** UserMappingPageClient의 셸 — 커넥터 연결과 같은 규칙(px-16, gap 40) */
function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <section className="bg-background-normal-normal mx-auto flex w-full flex-col gap-10 px-16 pt-9 pb-5 min-[1440px]:max-w-292">
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-xlarge text-text-normal-normal">이용자 매핑</h1>
        {/* UserMappingPageClient 실제 카피 그대로 */}
        <p className="text-body-small text-text-normal-alternative">CatchUp에서 사용하는 앱을 찾아 관리합니다.</p>
      </div>
      {children}
    </section>
  );
}

function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-heading-large text-text-normal-normal">{title}</h2>
      <p className="text-body-small text-text-normal-alternative">{description}</p>
    </div>
  );
}

/** 조회 화면 — 필터 칩이 표를 거르고(채널톡=1열) 페이지네이션이 붙는다 */
function UserMappingSurface(args: UserMappingScreenStoryArgs) {
  const [filter, setFilter] = useState<MappingStatusFilter>('all');
  const [page, setPage] = useState(1);

  const rows =
    filter === 'full'
      ? ROWS_FIXTURE.filter((row) => row.fullyMapped)
      : filter === 'partial'
        ? ROWS_FIXTURE.filter((row) => !row.fullyMapped)
        : ROWS_FIXTURE;

  return (
    <PageShell>
      <div className="flex flex-col gap-10">
        <section className="flex flex-col gap-4">
          <SectionHeader title="계정 등록 상태" description="팀의 매핑 등록 상태를 확인할 수 있어요." />
          <MappingStatCardRow items={STAT_FIXTURE} />
        </section>

        <section className="flex flex-col gap-4">
          <SectionHeader
            title="계정 매핑 상태"
            description="커넥터 탭을 누르면 완료율을 보면서 해당 커넥터의 매핑 현황으로 바로 걸러 볼 수 있어요."
          />
          <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
            <MappingFilterChips
              value={filter}
              onChange={(next) => {
                setFilter(next);
                setPage(1);
                args.onFilterChange(next);
              }}
            />
            <MappingActionsBar onSyncSso={fn()} onSyncDb={fn()} onOpenCsvUpload={fn()} onEdit={fn()} />
          </div>
          <UserMappingTable rows={rows} filterSource={filter === 'channel_talk' ? 'channel_talk' : null} />
          <Pagination
            currentPage={page}
            totalPages={3}
            onPageChange={(next) => {
              setPage(next);
              args.onPageChange(next);
            }}
          />
        </section>
      </div>
    </PageShell>
  );
}

/** 수정 모드 — 셀이 계정 드롭다운으로 바뀌고 우측 액션이 저장/취소가 된다 */
function UserMappingEditSurface() {
  const [overrides, setOverrides] = useState<Record<string, Partial<Record<MappingSource, AccountOverride>>>>({});

  return (
    <PageShell>
      <div className="flex flex-col gap-10">
        <section className="flex flex-col gap-4">
          <SectionHeader title="계정 등록 상태" description="팀의 매핑 등록 상태를 확인할 수 있어요." />
          <MappingStatCardRow items={STAT_FIXTURE} />
        </section>

        <section className="flex flex-col gap-4">
          <SectionHeader
            title="계정 매핑 상태"
            description="커넥터 탭을 누르면 완료율을 보면서 해당 커넥터의 매핑 현황으로 바로 걸러 볼 수 있어요."
          />
          <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
            <MappingFilterChips value="all" onChange={fn()} />
            <div className="flex items-center gap-2">
              <Button variant="box-outline-gray" size="md">
                취소
              </Button>
              <Button variant="box-solid-primary" size="md">
                저장하기
              </Button>
            </div>
          </div>
          <UserMappingTable
            rows={ROWS_FIXTURE}
            edit={{
              optionsByService: EDIT_OPTIONS,
              overrideOf: (rowId, source) => overrides[rowId]?.[source],
              onSelectAccount: (rowId, source, selected) =>
                setOverrides((prev) => ({
                  ...prev,
                  [rowId]: { ...prev[rowId], [source]: { type: 'account', account: selected } },
                })),
              onToggleUnused: (rowId, source, unused) =>
                setOverrides((prev) => {
                  const next = { ...prev[rowId] };
                  if (unused) next[source] = { type: 'unused' };
                  else delete next[source];
                  return { ...prev, [rowId]: next };
                }),
            }}
          />
        </section>
      </div>
    </PageShell>
  );
}

const meta = {
  title: 'Screens/Admin/User Mapping',
  tags: ['autodocs'],
  args: {
    onFilterChange: fn(),
    onPageChange: fn(),
  },
  argTypes: {
    onFilterChange: { control: false },
    onPageChange: { control: false },
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['default', 'channel-talk-filter', 'edit-mode', 'empty-csv-required', 'loading'],
      dataNotes: [
        '필터 fixture는 API 의미와 같게 걸렀다 — full/partial은 fullyMapped, 채널톡은 상태 필터가 아니라 1열 뷰 필터.',
        '수정 모드의 저장/취소·PATCH 배선은 붙이지 않는다(useUserMappingEdit) — 셀 드롭다운 상호작용만 로컬 state로 든다.',
      ],
      reuseNotes: ['골격은 UserMappingView와 같다: 통계 카드 섹션 → 필터/액션 한 줄 → 표 → 페이지네이션.'],
    }),
  },
} satisfies Meta<UserMappingScreenStoryArgs>;

export default meta;

type Story = StoryObj<UserMappingScreenStoryArgs>;

export const Default: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=17060-73886&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17060:73886',
      },
      viewport: { width: 1440, height: 900 },
      states: ['default', 'channel-talk-filter'],
    }),
  },
  render: (args) => <UserMappingSurface {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('기본 — 4열 전체 표', async () => {
      await expect(canvas.getByRole('columnheader', { name: 'Github' })).toBeInTheDocument();
      // 이용자 셀 + 계정 셀 3곳에 같은 이름이 나온다
      await expect(canvas.getAllByText('김수현').length).toBeGreaterThan(0);
    });

    await step('채널톡 칩 → 1열로 좁힌다', async () => {
      await userEvent.click(canvas.getByRole('tab', { name: '채널톡' }));
      await expect(args.onFilterChange).toHaveBeenCalledWith('channel_talk');
      await expect(canvas.queryByRole('columnheader', { name: 'Github' })).not.toBeInTheDocument();
      await expect(canvas.getByRole('columnheader', { name: '채널톡' })).toBeInTheDocument();
    });
  },
};

export const EditMode: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      // 수정 모드 화면은 신규 Figma가 없다 — 구버전 17379:92742 패턴 승계(감사 기록)
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['edit-mode'],
    }),
  },
  render: () => <UserMappingEditSurface />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('button', { name: '저장하기' })).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: '취소' })).toBeInTheDocument();
  },
};

export const EmptyCsvRequired: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      // 빈 상태는 구버전 안내 승계(사용자 승인 2026-08-04) — 신규 Figma 근거 없음
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['empty-csv-required'],
    }),
  },
  render: () => (
    <PageShell>
      <div className="flex flex-col gap-10">
        <section className="flex flex-col gap-4">
          <SectionHeader title="계정 등록 상태" description="팀의 매핑 등록 상태를 확인할 수 있어요." />
          <MappingStatCardRow items={STAT_FIXTURE.map((item) => ({ ...item, percent: 0, countLabel: '0/0' }))} />
        </section>
        <section className="flex flex-col gap-4">
          <SectionHeader
            title="계정 매핑 상태"
            description="커넥터 탭을 누르면 완료율을 보면서 해당 커넥터의 매핑 현황으로 바로 걸러 볼 수 있어요."
          />
          <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
            <MappingFilterChips value="all" onChange={fn()} />
            <MappingActionsBar onSyncSso={fn()} onSyncDb={fn()} onOpenCsvUpload={fn()} onEdit={fn()} />
          </div>
          <MappingSyncNotice variant="csv-required" />
          <UserMappingTable rows={[]} />
        </section>
      </div>
    </PageShell>
  ),
};

export const Loading: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['loading'],
    }),
  },
  render: () => (
    <PageShell>
      <div className="flex flex-col gap-10">
        <section className="flex flex-col gap-4">
          <SectionHeader title="계정 등록 상태" description="팀의 매핑 등록 상태를 확인할 수 있어요." />
          <MappingStatCardRow items={STAT_FIXTURE} />
        </section>
        <section className="flex flex-col gap-4">
          <SectionHeader
            title="계정 매핑 상태"
            description="커넥터 탭을 누르면 완료율을 보면서 해당 커넥터의 매핑 현황으로 바로 걸러 볼 수 있어요."
          />
          <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
            <MappingFilterChips value="all" onChange={fn()} />
            <MappingActionsBar onSyncSso={fn()} onSyncDb={fn()} onOpenCsvUpload={fn()} onEdit={fn()} />
          </div>
          <UserMappingTable rows={[]} isLoading skeletonCount={10} />
        </section>
      </div>
    </PageShell>
  ),
};
