'use client';

/** 조직 토큰 사용량 > 멤버 선택 모드 — 멤버 프로필 카드 (드롭다운 + 프로필 정보 + 액션 버튼) */

import { useMemo } from 'react';
import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import FilterDropdown, { type FilterOption } from '@/shared/components/ui/filter-dropdown';

import type { OrgMember } from '../../types/tokenUsageModel';

interface MemberProfileCardProps {
  members: OrgMember[];
  selectedMemberId: string;
  onSelectMember: (id: string) => void;
}

export default function MemberProfileCard({ members, selectedMemberId, onSelectMember }: MemberProfileCardProps) {
  const selectedMember = members.find((m) => m.id === selectedMemberId);

  const memberOptions = useMemo<FilterOption<string>[]>(
    () => members.map((m) => ({ value: m.id, label: `${m.name}(${m.team})` })),
    [members],
  );

  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-4 rounded-2xl border px-6 py-5">
      {/* 드롭다운 */}
      <FilterDropdown options={memberOptions} value={selectedMemberId} onChange={onSelectMember} />

      {/* 프로필 정보 */}
      {selectedMember && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* 프로필 이미지 */}
            {selectedMember.profileImage ? (
              <Image
                src={selectedMember.profileImage}
                alt={selectedMember.name}
                width={70}
                height={70}
                className="size-17.5 shrink-0 rounded-full object-cover"
              />
            ) : (
              <DefaultProfile className="text-text-normal-assistive size-17.5 shrink-0 rounded-full" />
            )}

            {/* 이름 + 상태 태그 + 팀/직책 */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2.5">
                <span className="text-heading-large text-text-normal-normal">{selectedMember.name}</span>
              </div>
              <span className="text-body-small text-text-normal-alternative">
                {selectedMember.team} · {selectedMember.position}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
