'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import dynamic from 'next/dynamic';

import { Button } from '@/shared/components/ui/button';
import Pagination from '@/shared/components/ui/pagination';

import { CONNECTOR_CONTENT } from '../../constants/connectorContent';
import { CONNECTOR_LOGOS } from '../../constants/connectorLogos';
import { useUserMappingEdit } from '../../hooks/useUserMappingEdit';
import { useUserMappingSync } from '../../hooks/useUserMappingSync';
import { userSourceMappingQueries } from '../../queries/userSourceMapping.queries';
import type { IntegrationService } from '../../types/integrationModel';
import type { MappingSource } from '../../types/userMappingModel';
import { mapUserMappingRows } from '../../utils/mapUserMappingRows';
import MappingActionsBar from '../user-mapping/MappingActionsBar';
import MappingFilterChips, { type MappingStatusFilter } from '../user-mapping/MappingFilterChips';
import MappingStatCardRow, { type MappingStatItem } from '../user-mapping/MappingStatCardRow';
import MappingSyncNotice from '../user-mapping/MappingSyncNotice';
import UserMappingTable from '../user-mapping/UserMappingTable';

const CsvUploadModal = dynamic(() => import('../user-mapping/CsvUploadModal'));

const PAGE_SIZE = 10;

/** 통계 카드 5종. 표시 전용이라 표 열(atlassian 합침 4종)과 대응할 필요가 없다 */
const STAT_ORDER: readonly (keyof typeof CONNECTOR_LOGOS)[] = ['jira', 'github', 'slack', 'confluence', 'channel_talk'];

/** atlassian 열은 수정 모드에서 jira 계정 후보·override 슬롯을 쓴다 — 백엔드 vendor 매핑이 jira=atlassian이라서다 */
const toEditService = (source: MappingSource): IntegrationService => (source === 'atlassian' ? 'jira' : source);

/**
 * /admin/user-mapping 화면. 스펙 ②(`2026-08-04-이용자매핑-리디자인-design.md`).
 *
 * 계정 등록 상태(통계 카드) → 계정 매핑 상태(필터 칩 + 액션 + 표 + 페이지네이션).
 * 통계 카드는 표시 전용이고, 표를 거르는 건 필터 칩뿐이다(사용자 결정 2026-08-04).
 * 앞 3개 칩은 API의 `mapping_status`(all/full/partial)와 1:1이고, 채널톡 칩만
 * 표를 1열로 좁히는 뷰 필터다.
 *
 * 감사에서 `MISSING`으로 남은 4건(목록 조회 실패 / 필터 결과 0명 / 카드 로딩·부분
 * 실패 / CSV 진행중)은 디자인 근거가 없어 구현하지 않는다.
 */
export default function UserMappingView() {
  const [filter, setFilter] = useState<MappingStatusFilter>('all');
  const [page, setPage] = useState(1);
  const [csvOpen, setCsvOpen] = useState(false);

  const statusQuery = useQuery(userSourceMappingQueries.status());
  // 채널톡 칩은 상태 필터가 아니라 뷰 필터라 조회는 all로 나간다
  const mappingStatus = filter === 'channel_talk' ? 'all' : filter;
  const listQuery = useQuery(userSourceMappingQueries.list({ mapping_status: mappingStatus, page, size: PAGE_SIZE }));

  // `?? []`를 인라인으로 두면 매 렌더 새 배열이라 아래 useMemo가 무의미해진다
  const items = useMemo(() => listQuery.data?.items ?? [], [listQuery.data?.items]);
  const rows = useMemo(() => mapUserMappingRows(items), [items]);
  const totalPages = Math.max(1, Math.ceil((listQuery.data?.total ?? 0) / PAGE_SIZE));

  const statItems: MappingStatItem[] = STAT_ORDER.map((key) => {
    const count = statusQuery.data?.[key];
    const users = count?.users ?? 0;
    const mapped = count?.mapped ?? 0;
    return {
      key,
      Logo: CONNECTOR_LOGOS[key],
      name: CONNECTOR_CONTENT[key as IntegrationService].name,
      percent: users > 0 ? Math.round((mapped / users) * 100) : 0,
      countLabel: `${mapped}/${users}`,
    };
  });

  const filterSource: MappingSource | null = filter === 'channel_talk' ? 'channel_talk' : null;

  // 수정 모드 — 구 UsersStatusSection 로직을 훅으로 공유한다
  const editUsers = useMemo(
    () =>
      items.map((item) => ({ userKey: String(item.user_id), sub: item.sub, email: item.email, userName: item.name })),
    [items],
  );
  const edit = useUserMappingEdit(editUsers);

  // 동기화 2종 — 토스트 문구까지 현행 구현 승계 (훅으로 추출)
  const sync = useUserMappingSync();

  const isEmpty = !listQuery.isLoading && rows.length === 0 && filter === 'all';

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-heading-large text-text-normal-normal">계정 등록 상태</h2>
          <p className="text-body-small text-text-normal-alternative">팀의 매핑 등록 상태를 확인할 수 있어요.</p>
        </div>
        <MappingStatCardRow items={statItems} />
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-heading-large text-text-normal-normal">계정 매핑 상태</h2>
          <p className="text-body-small text-text-normal-alternative">
            커넥터 탭을 누르면 완료율을 보면서 해당 커넥터의 매핑 현황으로 바로 걸러 볼 수 있어요.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
          <MappingFilterChips
            value={filter}
            onChange={(next) => {
              setFilter(next);
              setPage(1);
            }}
          />

          {edit.isEditMode ? (
            <div className="flex items-center gap-2">
              <Button variant="box-outline-gray" size="md" onClick={edit.cancel} disabled={edit.isSaving}>
                취소
              </Button>
              <Button variant="box-solid-primary" size="md" onClick={edit.save} disabled={edit.isSaving}>
                {edit.isSaving ? '저장 중...' : '저장하기'}
              </Button>
            </div>
          ) : (
            <MappingActionsBar
              onSyncSso={sync.syncSso}
              onSyncDb={sync.syncDb}
              onOpenCsvUpload={() => setCsvOpen(true)}
              onEdit={edit.startEdit}
              isSyncing={sync.isSyncing}
            />
          )}
        </div>

        {/* 매핑 데이터가 하나도 없을 때 — 구버전 승계(사용자 승인 2026-08-04) */}
        {isEmpty && <MappingSyncNotice variant="csv-required" />}

        <UserMappingTable
          rows={rows}
          filterSource={filterSource}
          isLoading={listQuery.isLoading}
          skeletonCount={PAGE_SIZE}
          edit={
            edit.isEditMode
              ? {
                  optionsByService: {
                    atlassian: edit.accountOptionsByService.jira,
                    github: edit.accountOptionsByService.github,
                    slack: edit.accountOptionsByService.slack,
                    channel_talk: edit.accountOptionsByService.channel_talk,
                  },
                  overrideOf: (rowId, source) => edit.overrides[rowId]?.[toEditService(source)],
                  onSelectAccount: (rowId, source, account) =>
                    edit.selectAccount(rowId, toEditService(source), account),
                  onToggleUnused: (rowId, source, unused) => edit.toggleUnused(rowId, toEditService(source), unused),
                }
              : undefined
          }
        />

        {totalPages > 1 && <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />}
      </section>

      <CsvUploadModal open={csvOpen} onOpenChange={setCsvOpen} />
    </div>
  );
}
