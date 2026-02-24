'use client';

/** 이용자 관리 > 테이블 (프로필 + 사용량 + 직급 + 부서 + 토글 + 케밥 메뉴) */

import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error.svg';
import IconChip from '@/public/icons/icon/chip.svg';
import IconGraph from '@/public/icons/icon/graph.svg';
import IconKebab from '@/public/icons/icon/kebab.svg';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Switch } from '@/shared/components/ui/switch';

import { POSITION_BADGE_CLASS, TEAM_BADGE_CLASS } from '../../constants/tokenUsageConfig';
import type { OrgMember } from '../../types/tokenUsage';

const TAG_BASE = 'text-body-xsmall inline-flex shrink-0 items-center truncate rounded-md2 px-1.5 py-0.5';

interface UserManagementTableProps {
  data: OrgMember[];
  onToggleToken: (member: OrgMember) => void;
}

export default function UserManagementTable({ data, onToggleToken }: UserManagementTableProps) {
  return (
    <div className="border-neutral-3 overflow-hidden rounded-xl border bg-white">
      {/* 헤더 */}
      <div className="text-heading-small bg-neutral-1 text-gray-70 grid grid-cols-[2fr_1fr_1fr_1fr_1fr] items-center px-5 py-1.5">
        <span>이름</span>
        <span>사용량</span>
        <span>직급</span>
        <span>부서</span>
        <span>토큰 사용</span>
      </div>

      {/* 행 */}
      {data.map((member) => (
        <div
          key={member.id}
          className="border-neutral-3 grid grid-cols-[2fr_1fr_1fr_1fr_1fr] items-center border-t px-5 py-3"
        >
          {/* 이름 */}
          <div className="flex items-center gap-2.5">
            {member.profileImage ? (
              <Image
                src={member.profileImage}
                alt={member.name}
                width={30}
                height={30}
                className="size-7.5 shrink-0 rounded-full object-cover"
              />
            ) : (
              <DefaultProfile className="border-neutral-2 text-gray-30 size-7.5 shrink-0 rounded-full border" />
            )}
            <span className="text-body-small text-gray-80 truncate">{member.name}</span>
            {!member.tokenEnabled && (
              <div className="rounded-md2 bg-pink-5 flex shrink-0 items-center gap-0.5 px-1.5 py-0.5">
                <IconError className="text-pink-60 size-3.5" />
                <span className="text-body-xsmall text-pink-60">이용 중지</span>
              </div>
            )}
          </div>

          {/* 사용량 */}
          <span className="text-body-small text-gray-80">{member.cost.toFixed(1)} $</span>

          {/* 직급 */}
          <div>
            <span className={`${TAG_BASE} ${POSITION_BADGE_CLASS[member.position] ?? 'bg-neutral-2 text-gray-50'}`}>
              {member.position}
            </span>
          </div>

          {/* 부서 */}
          <div>
            <span className={`${TAG_BASE} ${TEAM_BADGE_CLASS}`}>{member.team}</span>
          </div>

          {/* 토큰 사용 토글 + 케밥 */}
          <div className="flex items-center gap-2">
            <Switch checked={member.tokenEnabled} onCheckedChange={() => onToggleToken(member)} />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="icon-only-gray" size="sm" aria-label="더 보기">
                  <IconKebab className="size-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" sideOffset={4} className="min-w-[260px]">
                <DropdownMenuItem>
                  <IconGraph className="size-6 text-gray-50" />
                  토큰 이용 대시보드 바로가기
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <IconChip className="size-6 text-gray-50" />
                  개인 토큰 사용 제한 설정 바로가기
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      ))}
    </div>
  );
}
