'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconFilter from '@/public/icons/icon/filter-3.svg';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { useMemberStatusMutation } from '@/shared/queries/adminMembers.mutations';
import { adminMembersQueries } from '@/shared/queries/adminMembers.queries';
import { cn } from '@/shared/utils/cn';

import { DEACTIVATION_REASONS, ROLE_LABEL, SORT_OPTIONS } from '../../constants/memberTableConfig';
import type { AdminMember, AdminSortKey, MemberTableRow } from '../../types/adminMember';
import MemberDetailPanel from '../shared/MemberDetailPanel';
import MemberTable from '../shared/MemberTable';
import ReasonPopover from '../shared/ReasonPopover';
import SectionHeader from '../shared/SectionHeader';

interface UserListSectionProps {
  searchTerm: string;
}

/** 이용자 목록 섹션 */
const UserListSection = ({ searchTerm }: UserListSectionProps) => {
  const { data: members = [] } = useQuery(adminMembersQueries.list());
  const statusMutation = useMemberStatusMutation();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<AdminSortKey>('newest');

  /* 검색 필터 */
  const filtered = useMemo(() => members.filter((m) => m.name.includes(searchTerm)), [members, searchTerm]);

  /* 테이블 행 변환 */
  const tableRows: MemberTableRow[] = useMemo(
    () =>
      filtered.map((m) => ({
        key: m.userId,
        name: m.name,
        picture: m.picture,
        rank: m.rank,
        department: m.department,
        role: ROLE_LABEL[m.role] ?? m.role,
      })),
    [filtered],
  );

  /* 선택된 이용자 데이터 */
  const selectedMember: AdminMember | null = filtered.find((m) => m.userId === activeKey) ?? null;

  return (
    <section className="flex w-250 flex-col gap-3">
      <SectionHeader
        title="이용자 목록"
        count={filtered.length}
        description="이용자 현황을 확인하고 관리하세요."
        actions={
          <>
            <Button variant="box-outline-gray" size="md">
              <IconAddSmall className="size-5" />
              이용자 추가하기
            </Button>
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
                    className={cn(sortKey === option.key && 'bg-neutral-1')}
                  >
                    {option.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      <div className="border-neutral-3 grid h-124 min-h-0 w-250 grid-cols-[500px_500px] overflow-clip border-y">
        <MemberTable
          rows={tableRows}
          activeKey={activeKey}
          onSelectKey={setActiveKey}
          emptyMessage="등록된 이용자가 없습니다."
        />
        <MemberDetailPanel
          member={
            selectedMember
              ? {
                  name: selectedMember.name,
                  email: selectedMember.email,
                  department: selectedMember.department,
                  rank: selectedMember.rank,
                  picture: selectedMember.picture,
                  accountIds: selectedMember.accountIds,
                }
              : null
          }
          actionButtons={
            selectedMember && (
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
                  onSave={() =>
                    statusMutation.mutate({ userId: selectedMember.userId, action: 'deactivate' })
                  }
                />
                <Button
                  variant="box-outline-gray"
                  size="md"
                  className="text-red-50"
                  onClick={() => statusMutation.mutate({ userId: selectedMember.userId, action: 'delete' })}
                >
                  계정 삭제
                </Button>
              </>
            )
          }
        />
      </div>
    </section>
  );
};

export default UserListSection;
