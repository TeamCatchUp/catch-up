'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { JOB_LEVEL_LABEL } from '@/features/admin/members/constants/memberTableConfig';
import { adminMembersQueries } from '@/features/admin/members/queries/adminMembers.queries';
import QuestionLogListSection from '@/features/admin/question-logs/components/sections/QuestionLogListSection';
import SelectedUserProfile from '@/features/admin/question-logs/components/sections/SelectedUserProfile';
import UserSelectSection from '@/features/admin/question-logs/components/sections/UserSelectSection';

/** 관리자 — 이용자 질문 기록 페이지 */
export default function AdminQuestionLogsPage() {
  const [selectedUserId, setSelectedUserId] = useState('');

  const { data } = useQuery(adminMembersQueries.list());

  const userOptions = useMemo(
    () =>
      (data?.users ?? [])
        .filter((m) => m.status === 'active')
        .map((m) => ({
          id: m.id.toString(),
          name: m.name,
          department: m.department,
          rank: JOB_LEVEL_LABEL[m.jobLevel] ?? m.jobLevel,
          picture: null as string | null,
        })),
    [data?.users],
  );

  const selectedUser = userOptions.find((u) => u.id === selectedUserId);

  return (
    <section className="flex flex-col gap-4 px-16 pt-9 pb-25">
      <h1 className="text-heading-xlarge text-gray-80">이용자 질문 기록</h1>

      <div className="flex flex-col gap-8">
        <div className="bg-blue-1 flex flex-col rounded-xl p-4">
          <UserSelectSection users={userOptions} selectedUserId={selectedUserId} onUserChange={setSelectedUserId} />
        </div>

        {selectedUser && (
          <>
            <SelectedUserProfile user={selectedUser} />
            <QuestionLogListSection userId={Number(selectedUserId)} />
          </>
        )}
      </div>
    </section>
  );
}
