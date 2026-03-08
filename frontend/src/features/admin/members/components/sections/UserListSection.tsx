'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconFilter from '@/public/icons/icon/filter-3.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { cn } from '@/shared/utils/cn';

import {
  DEACTIVATION_REASONS,
  JOB_LEVEL_LABEL,
  SORT_OPTIONS,
  STATUS_BADGE_CLASS,
  STATUS_LABEL,
} from '../../constants/memberTableConfig';
import { useDeactivateUserMutation, useDeleteUserMutation } from '../../queries/adminMembers.mutations';
import { adminMembersQueries } from '../../queries/adminMembers.queries';
import type { AdminSortKey, MemberTableRow } from '../../types/adminMember';
import MemberDetailPanel from '../shared/MemberDetailPanel';
import MemberTable from '../shared/MemberTable';
import ReasonPopover from '../shared/ReasonPopover';
import SectionHeader from '../shared/SectionHeader';

interface UserListSectionProps {
  searchTerm: string;
}

/** 이용자 목록 섹션 */
const UserListSection = ({ searchTerm }: UserListSectionProps) => {
  const { data } = useQuery(adminMembersQueries.list());

  const deactivateMutation = useDeactivateUserMutation();
  const deleteMutation = useDeleteUserMutation();

  const [activeUserId, setActiveUserId] = useState<number | null>(null);
  const [sortKey, setSortKey] = useState<AdminSortKey>('newest');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  /* 검색 필터 */
  const filtered = useMemo(
    () => (data?.users ?? []).filter((m) => m.name.includes(searchTerm)),
    [data?.users, searchTerm],
  );

  /* 테이블 행 변환 */
  const tableRows: MemberTableRow[] = useMemo(
    () =>
      filtered.map((m) => ({
        key: m.id.toString(),
        name: m.name,
        picture: null,
        rank: JOB_LEVEL_LABEL[m.jobLevel] ?? m.jobLevel,
        department: m.department,
        lastColumn: STATUS_LABEL[m.status] ?? m.status,
      })),
    [filtered],
  );

  /* 선택된 이용자 */
  const selectedUser = filtered.find((m) => m.id === activeUserId) ?? null;
  const isAdmin = selectedUser?.role === 'admin';

  /* 상세 조회 */
  const { data: userDetail } = useQuery(adminMembersQueries.detail(activeUserId ?? 0));

  return (
    <section className="flex w-full flex-col gap-3">
      <SectionHeader
        title="이용자 목록"
        count={filtered.length}
        description="이용자 현황을 확인하고 관리하세요."
        actions={
          <>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="icon-outline-gray" size="md" className="size-9 p-1.5">
                  <IconFilter className="size-6" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" sideOffset={2} className="w-50 min-w-0">
                {SORT_OPTIONS.map((option) => (
                  <DropdownMenuItem
                    key={option.key}
                    onClick={() => setSortKey(option.key)}
                    className={cn(sortKey === option.key && 'bg-fill-strong')}
                  >
                    {option.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      <div className="border-edge-neutral grid h-124 min-h-0 grid-cols-2 overflow-clip border-y">
        <MemberTable
          rows={tableRows}
          activeKey={activeUserId?.toString() ?? null}
          onSelectKey={(key) => setActiveUserId(Number(key))}
          emptyMessage="이용자 목록이 없습니다."
          lastColumnHeader="상태"
          lastColumnBadgeClass={STATUS_BADGE_CLASS}
        />
        <MemberDetailPanel
          member={
            userDetail
              ? {
                  name: userDetail.name,
                  email: userDetail.email,
                  department: userDetail.department,
                  rank: JOB_LEVEL_LABEL[userDetail.jobLevel] ?? userDetail.jobLevel,
                  integrations: userDetail.integrations,
                }
              : null
          }
          actionButtons={
            selectedUser && !isAdmin ? (
              <>
                <ReasonPopover
                  trigger={
                    <Button variant="box-outline-gray" size="md">
                      비활성화
                    </Button>
                  }
                  title="비활성화 사유"
                  reasonLabel="비활성화 사유를 선택해주세요."
                  reasons={DEACTIVATION_REASONS}
                  onSave={(reason) => deactivateMutation.mutate({ userId: selectedUser.id, reason })}
                />
                <Button
                  variant="box-outline-gray"
                  size="md"
                  className="text-red-50"
                  onClick={() => setDeleteDialogOpen(true)}
                >
                  계정 삭제
                </Button>
                <ConfirmDialog
                  open={deleteDialogOpen}
                  onOpenChange={setDeleteDialogOpen}
                  title="해당 계정을 삭제하시겠어요?"
                  description="계정을 삭제하면 모든 데이터가 영구 삭제되며 복구할 수 없습니다."
                  confirmLabel="삭제"
                  variant="danger"
                  onConfirm={() => deleteMutation.mutate(selectedUser.id)}
                />
              </>
            ) : null
          }
        />
      </div>
    </section>
  );
};

export default UserListSection;
