'use client';

import { useState } from 'react';

import EntryRequestSection from '@/features/admin/members/components/sections/EntryRequestSection';
import UserListSection from '@/features/admin/members/components/sections/UserListSection';
import IconSearch from '@/public/icons/icon/search.svg';

/** 관리자 — 이용자 관리 페이지 */
export default function AdminMembersPage() {
  const [searchTerm, setSearchTerm] = useState('');

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-25">
      {/* 헤더: 타이틀 + 검색 */}
      <div className="flex flex-col gap-2.5">
        <h1 className="text-heading-xlarge text-content-normal">이용자 관리</h1>
        <label className="bg-fill-strong border-edge-assistive flex h-10 w-70 items-center gap-1.5 rounded-lg border px-3 py-2">
          <IconSearch className="text-content-assistive size-5 shrink-0" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="임직원의 이름을 검색하세요."
            className="text-body-small text-content-neutral placeholder:text-content-assistive w-full bg-transparent outline-none"
          />
        </label>
      </div>

      {/* 입장 신청 목록
      <EntryRequestSection searchTerm={searchTerm} /> */}

      {/* 이용자 목록 */}
      <UserListSection searchTerm={searchTerm} />
    </section>
  );
}
