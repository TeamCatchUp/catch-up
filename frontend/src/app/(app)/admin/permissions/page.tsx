'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AxiosError } from 'axios';

import AdminPromoteModal from '@/features/admin/permissions/components/modals/AdminPromoteModal';
import RoleChangeModal from '@/features/admin/permissions/components/modals/RoleChangeModal';
import PermissionsListSection from '@/features/admin/permissions/components/sections/PermissionsListSection';
import AdminOwnerInfoTag from '@/features/admin/permissions/components/shared/AdminOwnerInfoTag';
import {
  LIST_PAGE_SIZE,
  PROMOTE_ERROR_MESSAGES,
  REVOKE_ERROR_MESSAGES,
  ROLE_FILTER_OPTIONS,
  type RoleFilter,
} from '@/features/admin/permissions/constants/permissionsConfig';
import {
  usePromoteToAdminMutation,
  useRevokeAdminMutation,
} from '@/features/admin/permissions/queries/adminPermissions.mutations';
import { adminPermissionsQueries } from '@/features/admin/permissions/queries/adminPermissions.queries';
import type { PermissionMember } from '@/features/admin/permissions/types/adminPermission';
import type { ApiErrorBody } from '@/shared/api/errors';

const DEFAULT_ROLE_FILTER: RoleFilter = ROLE_FILTER_OPTIONS[0].key;

export default function AdminPermissionsPage() {
  const { data: members = [], isLoading, isError, refetch } = useQuery(adminPermissionsQueries.list());

  const promoteMutation = usePromoteToAdminMutation();
  const revokeMutation = useRevokeAdminMutation();

  const [changeModalOpen, setChangeModalOpen] = useState(false);
  const [selectedChangeMember, setSelectedChangeMember] = useState<PermissionMember | null>(null);

  const [roleChangeModalOpen, setRoleChangeModalOpen] = useState(false);
  const [selectedRoleChangeMember, setSelectedRoleChangeMember] = useState<PermissionMember | null>(null);

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

  const changeErrorMessage = useMemo(() => {
    if (!promoteMutation.isError) return undefined;
    const err = promoteMutation.error;
    if (err instanceof AxiosError && err.response?.data) {
      const body = err.response.data as ApiErrorBody;
      if (body.code) {
        return PROMOTE_ERROR_MESSAGES[body.code] ?? body.message ?? '권한 부여 요청에 실패했습니다.';
      }
    }
    return '권한 부여 요청에 실패했습니다.';
  }, [promoteMutation.isError, promoteMutation.error]);

  const revokeErrorMessage = useMemo(() => {
    if (!revokeMutation.isError) return undefined;
    const err = revokeMutation.error;
    if (err instanceof AxiosError && err.response?.data) {
      const body = err.response.data as ApiErrorBody;
      if (body.code) {
        return REVOKE_ERROR_MESSAGES[body.code] ?? body.message ?? '권한 변경 요청에 실패했습니다.';
      }
    }
    return '권한 변경 요청에 실패했습니다.';
  }, [revokeMutation.isError, revokeMutation.error]);

  const handleOpenChangeModal = (member: PermissionMember) => {
    promoteMutation.reset();
    setSelectedChangeMember(member);
    setChangeModalOpen(true);
  };

  const handleChangeSubmit = (userId: number, reason: string) => {
    promoteMutation.mutate(
      { userId, reason },
      {
        onSuccess: () => {
          setChangeModalOpen(false);
        },
      },
    );
  };

  const handleOpenRoleChangeModal = (member: PermissionMember) => {
    revokeMutation.reset();
    setSelectedRoleChangeMember(member);
    setRoleChangeModalOpen(true);
  };

  const handleRoleChangeSubmit = (userId: number, reason: string) => {
    revokeMutation.mutate(
      { userId, reason },
      {
        onSuccess: () => {
          setRoleChangeModalOpen(false);
        },
      },
    );
  };

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-25">
      <div className="flex items-center gap-2.5">
        <h1 className="text-heading-xlarge text-content-normal">권한 정보</h1>
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
          onRoleChangeClick={handleOpenRoleChangeModal}
        />
      </div>

      <AdminPromoteModal
        key={`change-${changeModalOpen ? 'open' : 'closed'}-${selectedChangeMember?.id}`}
        open={changeModalOpen}
        onOpenChange={setChangeModalOpen}
        member={selectedChangeMember}
        isSubmitting={promoteMutation.isPending}
        errorMessage={changeErrorMessage}
        onSubmit={handleChangeSubmit}
      />

      <RoleChangeModal
        key={`role-${roleChangeModalOpen ? 'open' : 'closed'}-${selectedRoleChangeMember?.id}`}
        open={roleChangeModalOpen}
        onOpenChange={setRoleChangeModalOpen}
        member={selectedRoleChangeMember}
        isSubmitting={revokeMutation.isPending}
        errorMessage={revokeErrorMessage}
        onSubmit={handleRoleChangeSubmit}
      />
    </section>
  );
}
