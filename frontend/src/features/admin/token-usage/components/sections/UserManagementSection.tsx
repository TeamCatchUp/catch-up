'use client';

/** 토큰 사용량 관리 > "이용자 관리" 탭 — 요약 + 정렬/검색 + 테이블 + 페이지네이션 + 토글 모달 */
// TODO: 이용자 관리 관련 API 구현 시 전면 교체 예정

import { useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import IconSearch from '@/public/icons/icon/search.svg';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';
import FilterDropdown, { type FilterOption } from '@/shared/components/ui/filter-dropdown';
import { Input } from '@/shared/components/ui/input';
import Pagination from '@/shared/components/ui/pagination';

import {
  USER_MGMT_SORT_OPTIONS,
  type UserMgmtSortKey,
  USERS_PER_PAGE,
} from '../../constants/tokenUsageConfig';
import { tokenUsageQueries } from '../../queries/tokenUsage.queries';
import type { OrgMember } from '../../types/tokenUsageModel';
import UserManagementTable from '../user-management/UserManagementTable';

const sortOptions: FilterOption<UserMgmtSortKey>[] = USER_MGMT_SORT_OPTIONS.map((o) => ({
  value: o.key,
  label: o.label,
}));

export default function UserManagementSection() {
  const { data: members } = useQuery(tokenUsageQueries.userManagement());

  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<UserMgmtSortKey>('newest');
  const [currentPage, setCurrentPage] = useState(1);
  const [dateRange, setDateRange] = useState<DateRange | undefined>();

  // 토글 모달 상태
  const [toggleTarget, setToggleTarget] = useState<OrgMember | null>(null);

  // 로컬 토글 상태 (mock용)
  const [localOverrides, setLocalOverrides] = useState<Record<string, boolean>>({});

  const getMemberEnabled = (member: OrgMember) => localOverrides[member.id] ?? false;

  // 검색 → 정렬 → 페이지네이션
  const processed = useMemo(() => {
    if (!members) return [];
    let result = members.map((m) => ({ ...m, tokenEnabled: getMemberEnabled(m) }));

    if (searchTerm) {
      result = result.filter((m) => m.name.includes(searchTerm));
    }

    switch (sortKey) {
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
        break;
      default:
        break;
    }

    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [members, searchTerm, sortKey, localOverrides]);

  const totalPages = Math.max(1, Math.ceil(processed.length / USERS_PER_PAGE));
  const paginated = processed.slice((currentPage - 1) * USERS_PER_PAGE, currentPage * USERS_PER_PAGE);

  // 토글 핸들러
  const handleToggleToken = (member: OrgMember) => {
    setToggleTarget(member);
  };

  const handleConfirmToggle = () => {
    if (!toggleTarget) return;
    const currentEnabled = getMemberEnabled(toggleTarget);
    setLocalOverrides((prev) => ({ ...prev, [toggleTarget.id]: !currentEnabled }));
    toast(currentEnabled ? '토큰 사용이 비활성화되었습니다.' : '토큰 사용이 활성화되었습니다.');
    setToggleTarget(null);
  };

  const handleSearch = (value: string) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  if (!members) return null;

  const isDisabling = toggleTarget ? getMemberEnabled(toggleTarget) : false;

  return (
    <div className="flex flex-col gap-6">
      {/* 헤더 행 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1.5">
          <span className="text-heading-small text-content-alternative">조직 전체 사용 토큰량</span>
          <span className="text-heading-xlarge text-content-normal">- $</span>
        </div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {/* 툴바: 정렬 + 검색 */}
      <div className="flex items-center justify-between">
        <FilterDropdown options={sortOptions} value={sortKey} onChange={setSortKey} />
        <div className="relative w-70">
          <IconSearch className="text-content-assistive pointer-events-none absolute top-1/2 left-2.5 size-5 -translate-y-1/2" />
          <Input
            inputSize="sm"
            placeholder="임직원의 이름을 검색해보세요."
            value={searchTerm}
            onChange={(e) => handleSearch(e.target.value)}
            className="border-edge-assistive bg-fill-strong pl-9"
          />
        </div>
      </div>

      {/* 테이블 */}
      <UserManagementTable data={paginated} onToggleToken={handleToggleToken} />

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
        </div>
      )}

      {/* 토글 확인 모달 */}
      {toggleTarget && (
        <ConfirmDialog
          open={!!toggleTarget}
          onOpenChange={(open) => !open && setToggleTarget(null)}
          title={
            isDisabling
              ? '해당 이용자의 토큰 사용을 비활성화하시겠습니까?'
              : '해당 이용자의 토큰 사용을 활성화하시겠습니까?'
          }
          description={
            isDisabling
              ? '비활성화 시 해당 이용자는 더 이상 AI 기능을 사용할 수 없으며, 기존에 할당된 잔여 토큰은 유지됩니다.'
              : '이용자의 토큰 사용 제한을 해제합니다. 이후 발생하는 토큰 사용량은 팀 사용량에 합산됩니다.'
          }
          confirmLabel={isDisabling ? '비활성화' : '활성화'}
          variant={isDisabling ? 'danger' : 'blue'}
          onConfirm={handleConfirmToggle}
        />
      )}
    </div>
  );
}
