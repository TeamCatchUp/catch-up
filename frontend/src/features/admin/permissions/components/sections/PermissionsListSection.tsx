import IconFilter from '@/public/icons/icon/filter-3.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import { ROLE_FILTER_OPTIONS, type RoleFilter } from '../../constants/permissionsConfig';
import type { PermissionMember } from '../../types/adminPermission';
import Pagination from '@/shared/components/ui/pagination';
import PermissionsTable from '../shared/PermissionsTable';

interface PermissionsListSectionProps {
  searchTerm: string;
  onSearchTermChange: (term: string) => void;
  roleFilter: RoleFilter;
  onRoleFilterChange: (filter: RoleFilter) => void;
  rows: PermissionMember[];
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onChangeRoleClick: (member: PermissionMember) => void;
}

/** 권한 목록 섹션 */
const PermissionsListSection = ({
  searchTerm,
  onSearchTermChange,
  roleFilter,
  onRoleFilterChange,
  rows,
  currentPage,
  totalPages,
  onPageChange,
  isLoading,
  isError,
  onRetry,
  onChangeRoleClick,
}: PermissionsListSectionProps) => {
  return (
    <section className="flex w-250 flex-col gap-3">
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-heading-large text-gray-80">권한 목록</h2>
          <p className="text-body-small text-gray-50">조직 내 사용자 권한을 체계적으로 관리합니다.</p>
        </div>

        <div className="flex items-center gap-2">
          <label className="bg-neutral-1 border-neutral-2 flex h-10 w-70 items-center gap-1.5 rounded-lg border px-3 py-2">
            <IconSearch className="text-gray-30 size-5 shrink-0" />
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => onSearchTermChange(event.target.value)}
              placeholder="담당자 또는 스페이스를 검색하세요."
              className="text-body-small text-gray-70 placeholder:text-gray-30 w-full bg-transparent outline-none"
            />
          </label>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="icon-outline-gray" size="md" className="size-9 p-1.5">
                <IconFilter className="size-6" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" sideOffset={2} className="w-32 min-w-0">
              {ROLE_FILTER_OPTIONS.map((option) => (
                <DropdownMenuItem
                  key={option.key}
                  onClick={() => onRoleFilterChange(option.key)}
                  className={cn(roleFilter === option.key && 'bg-neutral-1')}
                >
                  {option.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex h-[872px] flex-col overflow-hidden bg-white">
        {isLoading ? (
          <div className="flex h-full flex-col gap-3 p-5">
            <div className="bg-neutral-2 h-9 animate-pulse rounded-lg" />
            {Array.from({ length: 10 }).map((_, index) => (
              <div key={index} className="bg-neutral-1 rounded-md2 h-12.5 animate-pulse" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex h-full flex-col items-center justify-center gap-3">
            <p className="text-body-small text-gray-50">권한 목록을 불러오지 못했습니다.</p>
            <Button variant="box-outline-gray" size="md" onClick={onRetry}>
              재시도
            </Button>
          </div>
        ) : (
          <>
            <PermissionsTable rows={rows} onChangeRoleClick={onChangeRoleClick} />
            <div className="flex h-21 shrink-0 items-center justify-center">
              <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />
            </div>
          </>
        )}
      </div>
    </section>
  );
};

export default PermissionsListSection;
