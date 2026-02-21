'use client';

import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconFilter from '@/public/icons/icon/filter-3.svg';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Separator } from '@/shared/components/ui/separator';
import { useDecideRequestMutation } from '@/shared/queries/adminMembers.mutations';
import { adminMembersQueries } from '@/shared/queries/adminMembers.queries';
import { cn } from '@/shared/utils/cn';

import { REJECTION_REASONS, ROLE_BADGE_CLASS, ROLE_LABEL, SORT_OPTIONS } from '../../constants/memberTableConfig';
import type { AdminSortKey, EntryRequest, MemberTableRow } from '../../types/adminMember';
import MemberDetailPanel from '../shared/MemberDetailPanel';
import MemberTable from '../shared/MemberTable';
import ReasonPopover from '../shared/ReasonPopover';
import SectionHeader from '../shared/SectionHeader';

interface EntryRequestSectionProps {
  searchTerm: string;
}

/** 입장 신청 목록 섹션 */
const EntryRequestSection = ({ searchTerm }: EntryRequestSectionProps) => {
  const { data: requests = [] } = useQuery(adminMembersQueries.requests());
  const decideMutation = useDecideRequestMutation();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<AdminSortKey>('newest');
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  /* 검색 필터 */
  const filtered = useMemo(() => requests.filter((r) => r.name.includes(searchTerm)), [requests, searchTerm]);

  /* 테이블 행 변환 */
  const tableRows: MemberTableRow[] = useMemo(
    () =>
      filtered.map((r) => ({
        key: r.requestId,
        name: r.name,
        picture: r.picture,
        rank: r.rank,
        department: r.department,
        lastColumn: ROLE_LABEL[r.role] ?? r.role,
      })),
    [filtered],
  );

  /* 선택된 신청자 데이터 */
  const selectedRequest: EntryRequest | null = filtered.find((r) => r.requestId === activeKey) ?? null;

  /* 승인/반려 핸들러 */
  const handleDecide = (requestIds: string[], decision: 'approve' | 'reject') => {
    decideMutation.mutate({ requestIds, decision });
  };

  /* 체크박스 선택 핸들러 */
  const handleToggleKey = useCallback((key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else {
        next.add(key);
        setActiveKey(key);
      }
      return next;
    });
  }, []);

  const handleToggleAll = useCallback(() => {
    setSelectedKeys((prev) =>
      prev.size === tableRows.length ? new Set() : new Set(tableRows.map((r) => r.key)),
    );
  }, [tableRows]);

  const handleCancelSelection = () => {
    setSelectedKeys(new Set());
    setIsSelecting(false);
  };

  return (
    <section className="flex w-250 flex-col gap-3">
      <SectionHeader
        title="입장 신청 목록"
        count={filtered.length}
        description="신규 회원의 가입 요청을 확인하고 승인하세요."
        actions={
          <>
            <div className="border-neutral-3 flex items-center gap-0.5 rounded-lg border bg-white px-2 py-0.5">
              <Button
                variant="text-secondary-mono"
                size="md"
                onClick={() =>
                  handleDecide(
                    filtered.map((r) => r.requestId),
                    'reject',
                  )
                }
              >
                전체 반려하기
              </Button>
              <Separator orientation="vertical" className="h-6" />
              <Button
                variant="text-secondary-mono"
                size="md"
                className="text-green-40"
                onClick={() =>
                  handleDecide(
                    filtered.map((r) => r.requestId),
                    'approve',
                  )
                }
              >
                전체 승인하기
              </Button>
            </div>
            <Button
              variant="box-outline-gray"
              size="md"
              className="text-body-small h-9"
              onClick={isSelecting ? handleCancelSelection : () => setIsSelecting(true)}
            >
              {isSelecting ? '모두 선택 취소' : '선택하기'}
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
          emptyMessage="입장 신청 내역이 없습니다."
          lastColumnHeader="권한"
          lastColumnBadgeClass={ROLE_BADGE_CLASS}
          isSelecting={isSelecting}
          selectedKeys={selectedKeys}
          onToggleKey={handleToggleKey}
          onToggleAll={handleToggleAll}
        />
        <MemberDetailPanel
          member={
            selectedRequest
              ? {
                  name: selectedRequest.name,
                  email: selectedRequest.email,
                  department: selectedRequest.department,
                  rank: selectedRequest.rank,
                  picture: selectedRequest.picture,
                  accountIds: selectedRequest.accountIds,
                }
              : null
          }
          actionButtons={
            selectedRequest && (
              <>
                <ReasonPopover
                  trigger={
                    <Button variant="box-outline-gray" size="md">
                      반려
                    </Button>
                  }
                  title="반려 사유"
                  reasonLabel="반려 사유를 선택해주세요."
                  reasons={REJECTION_REASONS}
                  onSave={() => handleDecide([selectedRequest.requestId], 'reject')}
                />
                <Button
                  variant="box-outline-gray"
                  size="md"
                  className="text-green-40"
                  onClick={() => handleDecide([selectedRequest.requestId], 'approve')}
                >
                  승인
                </Button>
              </>
            )
          }
        />
      </div>
    </section>
  );
};

export default EntryRequestSection;
