'use client';

import { useCallback, useMemo, useState } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dynamic from 'next/dynamic';
import { toast } from 'sonner';

import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import { Button } from '@/shared/components/ui/button';
import Pagination from '@/shared/components/ui/pagination';
import { cn } from '@/shared/utils/cn';

import { adminConnectorMutations } from '../../../queries/adminConnector.mutations';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type {
  PreMappingBulkUpdateResponse,
  PreMappingUpdateItem,
  SyncFilterType,
  VendorType,
} from '../../../types/integrationApi';
import type { IntegrationService } from '../../../types/integrationModel';
import type { MemberDisplayRow } from '../../../types/memberDisplayModel';
import type { AccountOption } from '../tables/AccountSelectDropdown';
import UsersTable from '../tables/UsersTable';

const CsvUploadModal = dynamic(() => import('../modals/CsvUploadModal'));

const PAGE_SIZE = 10;

interface UsersStatusSectionProps {
  total: number;
  displayRows: MemberDisplayRow[];
  filterType: SyncFilterType;
  onFilterChange: (type: SyncFilterType) => void;
  currentPage: number;
  onPageChange: (page: number) => void;
}

const FILTER_OPTIONS: { key: SyncFilterType; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'full', label: '모두 연동된 이용자' },
  { key: 'partial', label: '연동되지 않은 이용자' },
];

/** 이용자 계정 연동 상태 섹션 */
export default function UsersStatusSection({
  total,
  displayRows,
  filterType,
  onFilterChange,
  currentPage,
  onPageChange,
}: UsersStatusSectionProps) {
  const [isEditMode, setIsEditMode] = useState(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);

  // ─── 툴별 사용자 목록 (수정 모드 드롭다운용) ───
  const githubUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'github' }),
    enabled: isEditMode,
  });
  const atlassianUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'atlassian' }),
    enabled: isEditMode,
  });
  const slackUsers = useInfiniteQuery({
    ...adminConnectorQueries.vendorUsers({ vendorType: 'slack' }),
    enabled: isEditMode,
  });

  const accountOptionsByService = useMemo<Partial<Record<IntegrationService, AccountOption[]>>>(() => {
    if (!isEditMode) return {};

    const toOptions = (
      pages: { items: { id: string; name: string; identifier: string | null; picture: string | null }[] }[] | undefined,
    ): AccountOption[] =>
      pages?.flatMap((page) =>
        page.items.map((item) => ({
          id: item.id,
          name: item.name,
          identifier: item.identifier ?? '',
          picture: item.picture,
        })),
      ) ?? [];

    return {
      github: toOptions(githubUsers.data?.pages),
      jira: toOptions(atlassianUsers.data?.pages),
      slack: toOptions(slackUsers.data?.pages),
    };
  }, [isEditMode, githubUsers.data?.pages, atlassianUsers.data?.pages, slackUsers.data?.pages]);

  // 수정 모드에서 계정 선택 / 미사용 토글 로컬 오버라이드
  type AccountOverride = { type: 'account'; account: AccountOption } | { type: 'unused' };
  const [overrides, setOverrides] = useState<Record<string, Partial<Record<IntegrationService, AccountOverride>>>>({});

  const handleAccountSelect = useCallback((userKey: string, service: IntegrationService, account: AccountOption) => {
    setOverrides((prev) => ({
      ...prev,
      [userKey]: { ...prev[userKey], [service]: { type: 'account', account } },
    }));
  }, []);

  const handleToggleUnused = useCallback((userKey: string, service: IntegrationService, unused: boolean) => {
    setOverrides((prev) => {
      const userOverrides = { ...prev[userKey] };
      if (unused) {
        userOverrides[service] = { type: 'unused' };
      } else {
        delete userOverrides[service];
      }
      return { ...prev, [userKey]: userOverrides };
    });
  }, []);

  // ─── SSO 동기화 mutation ───
  const syncOAuthMutation = useMutation({
    ...adminConnectorMutations.syncOAuthUsers(),
    onSuccess: () => {
      toast('동기화가 완료되었습니다.', { description: 'SSO 사용자 정보가 반영되었습니다.' });
    },
    onError: () => {
      toast('일시적인 오류가 발생했습니다.', { description: '잠시 후 다시 시도해주세요.' });
    },
  });

  // ─── 저장 mutation ───
  // 채널톡은 organization-level 연동이라 user-level vendor mapping 없음 → Partial로 표현
  const SERVICE_TO_VENDOR: Partial<Record<IntegrationService, VendorType>> = {
    jira: 'atlassian',
    confluence: 'atlassian',
    github: 'github',
    slack: 'slack',
  };

  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationKey: ['admin', 'preMappings', 'bulk'] as const,
    mutationFn: async () => {
      // overrides를 vendor별로 그룹핑
      const byVendor: Partial<Record<VendorType, PreMappingUpdateItem[]>> = {};

      for (const [userKey, serviceOverrides] of Object.entries(overrides)) {
        const row = displayRows.find((r) => r.row.userKey === userKey)?.row;
        if (!row) continue;

        for (const [service, override] of Object.entries(serviceOverrides) as [IntegrationService, AccountOverride][]) {
          const vendor = SERVICE_TO_VENDOR[service];
          if (!vendor) continue; // channel-talk 등 vendor mapping 없는 서비스는 skip
          if (!byVendor[vendor]) byVendor[vendor] = [];

          byVendor[vendor]!.push({
            sub: row.userKey,
            email: row.email,
            name: row.userName,
            is_ignored: override.type === 'unused',
            external_user_identifier: override.type === 'account' ? override.account.id : null,
          });
        }
      }

      // vendor별 병렬 PATCH
      const requests = Object.entries(byVendor).map(([vendor, items]) =>
        api.patch<PreMappingBulkUpdateResponse>(API.admin.preMappingsBulk(vendor), { items }),
      );

      return Promise.all(requests);
    },
    onSuccess: () => {
      toast('저장이 완료되었습니다.', { description: '계정 연동 정보가 반영되었습니다.' });
      queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'syncStatus'] });
      setOverrides({});
      setIsEditMode(false);
    },
    onError: () => {
      toast('일시적인 오류가 발생했습니다.', { description: '잠시 후 다시 시도해주세요.' });
    },
  });

  const handleSave = () => {
    if (saveMutation.isPending) return;
    if (Object.keys(overrides).length === 0) {
      setIsEditMode(false);
      return;
    }
    saveMutation.mutate();
  };

  // 오버라이드 적용된 행
  const effectiveRows = useMemo(() => {
    if (Object.keys(overrides).length === 0) return displayRows;

    return displayRows.map((displayRow) => {
      const userOverrides = overrides[displayRow.row.userKey];
      if (!userOverrides) return displayRow;

      const newStatus = { ...displayRow.displayStatusByService };

      for (const [service, override] of Object.entries(userOverrides) as [IntegrationService, AccountOverride][]) {
        if (override.type === 'unused') {
          newStatus[service] = '미사용';
        }
      }

      return {
        ...displayRow,
        displayStatusByService: newStatus,
      };
    });
  }, [displayRows, overrides]);

  // override에서 선택된 계정만 추출 (드롭다운 트리거 표시용)
  const selectedAccounts = useMemo(() => {
    const result: Record<string, Partial<Record<IntegrationService, AccountOption>>> = {};
    for (const [userKey, serviceOverrides] of Object.entries(overrides)) {
      for (const [service, override] of Object.entries(serviceOverrides) as [IntegrationService, AccountOverride][]) {
        if (override.type === 'account') {
          if (!result[userKey]) result[userKey] = {};
          result[userKey]![service] = override.account;
        }
      }
    }
    return result;
  }, [overrides]);

  // 서버 사이드 페이지네이션
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="flex w-full flex-col gap-3">
      {/* 헤더: 제목 + 설명 */}
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-content-normal">
          이용자 계정 등록 상태 <span className="text-content-primary-assistive">{total}</span>
        </h2>
        <p className="text-body-small text-content-alternative">
          Catch Up 사용자의 협업 툴 계정 등록 상태를 확인할 수 있어요.
        </p>
      </div>

      {/* 필터 칩 + 버튼 영역 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* 필터 칩 */}
        <div className="flex items-center gap-2">
          {FILTER_OPTIONS.map(({ key, label }) => {
            const isSelected = filterType === key;

            return (
              <button
                key={key}
                onClick={() => onFilterChange(key)}
                className={cn(
                  'text-body-small h-9 cursor-pointer rounded-full border px-3 py-1.5 transition-colors',
                  isSelected
                    ? 'bg-neutral-80 border-transparent text-white'
                    : 'border-edge-neutral text-content-alternative',
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* 버튼 영역 */}
        <div className="flex items-center gap-2">
          <Button
            variant="box-outline-gray"
            size="md"
            className="text-body-small h-9"
            disabled={syncOAuthMutation.isPending}
            onClick={() => syncOAuthMutation.mutate()}
          >
            SSO User 동기화
          </Button>

          <Button
            variant="box-outline-gray"
            size="md"
            className="text-body-small h-9"
            onClick={() => setIsCsvModalOpen(true)}
          >
            CSV 일괄등록
          </Button>

          {isEditMode ? (
            <Button
              variant="box-solid-primary"
              size="md"
              className="text-body-small h-9"
              disabled={saveMutation.isPending}
              onClick={handleSave}
            >
              {saveMutation.isPending ? '저장 중...' : '저장하기'}
            </Button>
          ) : (
            <Button
              variant="box-outline-gray"
              size="md"
              className="text-body-small flex h-9 items-center gap-1.5"
              onClick={() => setIsEditMode(true)}
            >
              <IconEditPencil className="h-4 w-4" />
              수정하기
            </Button>
          )}
        </div>
      </div>

      {/* 테이블 */}
      <div className="border-edge-neutral w-full border-y">
        <UsersTable
          displayRows={effectiveRows}
          isEditMode={isEditMode}
          accountOptionsByService={accountOptionsByService}
          selectedAccounts={selectedAccounts}
          onAccountSelect={handleAccountSelect}
          onToggleUnused={handleToggleUnused}
        />
      </div>

      {/* 페이지네이션 + 범례 */}
      <div className="flex items-center justify-between px-4 py-2">
        <div className="flex-1" />
        {totalPages > 1 && <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />}
        <div className="flex flex-1 items-center justify-end gap-6">
          <div className="flex items-center gap-2">
            <div className="bg-status-positive h-2.5 w-2.5 rounded-full" />
            <p className="text-body-small text-content-alternative">모두 연동된 이용자</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="bg-accent-red h-2.5 w-2.5 rounded-full" />
            <p className="text-body-small text-content-alternative">연동되지 않은 이용자</p>
          </div>
        </div>
      </div>

      {/* CSV 업로드 모달 */}
      <CsvUploadModal open={isCsvModalOpen} onOpenChange={setIsCsvModalOpen} />
    </section>
  );
}
