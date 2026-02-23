'use client';

/** 조직 토큰 사용량 > 멤버 선택 모드 — 멤버 프로필 카드 (드롭다운 + 프로필 정보 + 액션 버튼) */

import { useMemo } from 'react';
import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error.svg';
import IconKebab from '@/public/icons/icon/kebab.svg';
import { Button } from '@/shared/components/ui/button';
import FilterDropdown, { type FilterOption } from '@/shared/components/ui/filter-dropdown';

import type { OrgMember } from '../../types/tokenUsage';

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
    <div className="flex flex-col gap-4 rounded-2xl border border-neutral-3 bg-white px-6 py-5">
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
              <DefaultProfile className="size-17.5 shrink-0 rounded-full border border-neutral-2 text-gray-30" />
            )}

            {/* 이름 + 상태 태그 + 팀/직책 */}
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2.5">
                <span className="text-heading-large text-gray-80">{selectedMember.name}</span>
                <div className="flex items-center gap-1 rounded-md2 bg-pink-5 px-1.5 py-0.5">
                  <IconError className="size-4 text-pink-60" />
                  <span className="text-body-xsmall text-pink-60">이용 중지</span>
                </div>
              </div>
              <span className="text-body-small text-gray-50">
                {selectedMember.team} · {selectedMember.position}
              </span>
            </div>
          </div>

          {/* 액션 버튼 */}
          <div className="flex shrink-0 items-center gap-1.5">
            <Button variant="capsule-outline-blue" size="sm">
              이용 중지 해제
            </Button>
            <Button variant="icon-only-gray" size="lg" aria-label="더 보기">
              <IconKebab className="size-6" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
