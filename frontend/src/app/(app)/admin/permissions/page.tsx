'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import PermissionChangeModal from '@/features/admin/permissions/components/modals/PermissionChangeModal';
import PermissionsListSection from '@/features/admin/permissions/components/sections/PermissionsListSection';
import AdminOwnerInfoTag from '@/features/admin/permissions/components/shared/AdminOwnerInfoTag';
import {
  LIST_PAGE_SIZE,
  ROLE_FILTER_OPTIONS,
  type RoleFilter,
} from '@/features/admin/permissions/constants/permissionsConfig';
import { usePromoteToAdminMutation } from '@/features/admin/permissions/queries/adminPermissions.mutations';
import { adminPermissionsQueries } from '@/features/admin/permissions/queries/adminPermissions.queries';
import type { PermissionMember } from '@/features/admin/permissions/types/adminPermission';

const DEFAULT_ROLE_FILTER: RoleFilter = ROLE_FILTER_OPTIONS[0].key;

export default function AdminPermissionsPage() {
  const { data: members = [], isLoading, isError, refetch } = useQuery(adminPermissionsQueries.list());

  const promoteMutation = usePromoteToAdminMutation();

  const [changeModalOpen, setChangeModalOpen] = useState(false);
  const [selectedChangeMemberId, setSelectedChangeMemberId] = useState<number | null>(null);

  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<RoleFilter>(DEFAULT_ROLE_FILTER);
  const [currentPage, setCurrentPage] = useState(1);

  const filteredMembers = useMemo(() => {
    const keyword = searchTerm.trim();

    return members.filter((member) => {
      const matchedSearch = !keyword || member.name.includes(keyword) || member.department.includes(keyword);
      const matchedRole = roleFilter === 'all' || member.role === roleFilter;
      return matchedSearch && matchedRole;
    });
  }, [members, roleFilter, searchTerm]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(filteredMembers.length / LIST_PAGE_SIZE)),
    [filteredMembers.length],
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const pagedMembers = useMemo(() => {
    const start = (safeCurrentPage - 1) * LIST_PAGE_SIZE;
    return filteredMembers.slice(start, start + LIST_PAGE_SIZE);
  }, [filteredMembers, safeCurrentPage]);

  const changeErrorMessage = promoteMutation.isError
    ? ((promoteMutation.error as Error | null)?.message ?? '권한 부여 요청에 실패했습니다.')
    : undefined;

  const handleOpenChangeModal = (member: PermissionMember) => {
    promoteMutation.reset();
    setSelectedChangeMemberId(member.id);
    setChangeModalOpen(true);
  };

  const handleChangeSubmit = (userId: number) => {
    promoteMutation.mutate(userId, {
      onSuccess: () => {
        setChangeModalOpen(false);
      },
    });
  };

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-25">
      <div className="flex items-center gap-2.5">
        <h1 className="text-heading-xlarge text-gray-80">권한 정보</h1>
        <AdminOwnerInfoTag />
      </div>

      <div className="flex flex-col gap-8">
        <PermissionsListSection
          searchTerm={searchTerm}
          onSearchTermChange={(term) => {
            setSearchTerm(term);
            setCurrentPage(1);
          }}
          roleFilter={roleFilter}
          onRoleFilterChange={(nextFilter) => {
            setRoleFilter(nextFilter);
            setCurrentPage(1);
          }}
          rows={pagedMembers}
          currentPage={safeCurrentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          isLoading={isLoading}
          isError={isError}
          onRetry={() => {
            void refetch();
          }}
          onChangeRoleClick={handleOpenChangeModal}
        />
      </div>

      <PermissionChangeModal
        key={`change-${changeModalOpen ? 'open' : 'closed'}-${selectedChangeMemberId}`}
        open={changeModalOpen}
        onOpenChange={setChangeModalOpen}
        members={members}
        initialMemberId={selectedChangeMemberId}
        isSubmitting={promoteMutation.isPending}
        errorMessage={changeErrorMessage}
        onSubmit={handleChangeSubmit}
      />
    </section>
  );
}
