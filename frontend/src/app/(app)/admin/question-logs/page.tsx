'use client';

import { useMemo, useState } from 'react';

import QuestionLogListSection from '@/features/admin/question-logs/components/sections/QuestionLogListSection';
import SelectedUserProfile from '@/features/admin/question-logs/components/sections/SelectedUserProfile';
import UserSelectSection from '@/features/admin/question-logs/components/sections/UserSelectSection';
import { MOCK_QUESTION_LOGS } from '@/features/admin/question-logs/mocks/questionLogsMockData';
import { MOCK_ADMIN_MEMBERS } from '@/shared/mocks/admin/adminMembersMockData';

/** 관리자 — 이용자 질문 기록 페이지 */
export default function AdminQuestionLogsPage() {
  const [selectedUserId, setSelectedUserId] = useState('');

  const userOptions = useMemo(
    () =>
      MOCK_ADMIN_MEMBERS.filter((m) => m.status === 'active').map((m) => ({
        id: m.userId,
        name: m.name,
        department: m.department,
        rank: m.rank,
        picture: m.picture,
      })),
    [],
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
            <QuestionLogListSection items={MOCK_QUESTION_LOGS} userId={selectedUserId} />
          </>
        )}
      </div>
    </section>
  );
}
