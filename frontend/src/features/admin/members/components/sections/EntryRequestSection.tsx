'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import IconFilter from '@/public/icons/icon/filter-3.svg';
import { Button } from '@/shared/components/ui/button';
import { Separator } from '@/shared/components/ui/separator';
import { useDecideRequestMutation } from '@/shared/queries/adminMembers.mutations';
import { adminMembersQueries } from '@/shared/queries/adminMembers.queries';

import { ROLE_LABEL } from '../../constants/memberTableConfig';
import type { EntryRequest, MemberTableRow } from '../../types/adminMember';
import MemberDetailPanel from '../shared/MemberDetailPanel';
import MemberTable from '../shared/MemberTable';
import SectionHeader from '../shared/SectionHeader';

interface EntryRequestSectionProps {
  searchTerm: string;
}

/** 입장 신청 목록 섹션 */
const EntryRequestSection = ({ searchTerm }: EntryRequestSectionProps) => {
  const { data: requests = [] } = useQuery(adminMembersQueries.requests());
  const decideMutation = useDecideRequestMutation();
  const [activeKey, setActiveKey] = useState<string | null>(null);

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
        role: ROLE_LABEL[r.role] ?? r.role,
      })),
    [filtered],
  );

  /* 선택된 신청자 데이터 */
  const selectedRequest: EntryRequest | null = filtered.find((r) => r.requestId === activeKey) ?? null;

  /* 승인/반려 핸들러 */
  const handleDecide = (requestIds: string[], decision: 'approve' | 'reject') => {
    decideMutation.mutate({ requestIds, decision });
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
            <Button variant="box-outline-gray" size="md" className="text-body-small h-9">
              선택하기
            </Button>
            <Button variant="icon-outline-gray" size="md" className="size-9 p-1.5">
              <IconFilter className="size-6" />
            </Button>
          </>
        }
      />

      <div className="border-neutral-3 grid h-124 min-h-0 w-250 grid-cols-[500px_500px] overflow-clip border-y">
        <MemberTable
          rows={tableRows}
          activeKey={activeKey}
          onSelectKey={setActiveKey}
          emptyMessage="입장 신청 내역이 없습니다."
        />
        <MemberDetailPanel
          member={
            selectedRequest
              ? {
                  name: selectedRequest.name,
                  phone: selectedRequest.phone,
                  email: selectedRequest.email,
                  department: selectedRequest.department,
                  teamSize: selectedRequest.teamSize,
                  picture: selectedRequest.picture,
                  accountIds: selectedRequest.accountIds,
                }
              : null
          }
          actionButtons={
            selectedRequest && (
              <>
                <Button
                  variant="box-outline-gray"
                  size="md"
                  onClick={() => handleDecide([selectedRequest.requestId], 'reject')}
                >
                  반려
                </Button>
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
