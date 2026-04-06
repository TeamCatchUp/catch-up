'use client';

/** 조직 토큰 사용량 > 토큰 사용량 순위 리스트 (스크롤 가능) */

import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { Badge } from '@/shared/components/ui/badge';

import type { TokenUsageRankingEntry } from '../../types/tokenUsageModel';

interface TokenUsageRankingListProps {
  data: TokenUsageRankingEntry[];
}

export default function TokenUsageRankingList({ data }: TokenUsageRankingListProps) {
  return (
    <div className="border-edge-neutral bg-fill-normal flex h-full flex-col overflow-hidden rounded-md border">
      {/* 헤더 */}
      <div className="bg-fill-strong rounded-md px-5 py-1.5">
        <span className="text-heading-small text-content-neutral">토큰 사용량 순위</span>
      </div>

      {/* 스크롤 리스트 */}
      <div className="flex-1 overflow-y-auto">
        {data.map((entry, index) => (
          <div
            key={entry.member.id}
            className={`flex items-center gap-3 px-5 py-3 ${index < data.length - 1 ? 'border-edge-neutral border-b' : ''}`}
          >
            {/* 순위 */}
            <span className="text-body-small text-content-alternative w-5 shrink-0 text-center">{entry.rank}</span>

            {/* 프로필 이미지 */}
            {entry.member.profileImage ? (
              <Image
                src={entry.member.profileImage}
                alt={entry.member.name}
                width={30}
                height={30}
                className="size-7.5 shrink-0 rounded-full object-cover"
              />
            ) : (
              <DefaultProfile className="text-content-assistive size-7.5 shrink-0 rounded-full" />
            )}

            {/* 이름 */}
            <span className="text-body-small text-content-normal w-15.5 shrink-0 truncate">{entry.member.name}</span>

            {/* 팀 태그 */}
            <Badge variant="success" size="sm" className="rounded-md2 shrink-0 px-1.5 py-0.5">
              {entry.member.team}
            </Badge>

            {/* 비용 (우측 정렬) */}
            <span className="text-body-small text-content-normal ml-auto shrink-0 text-right">
              {entry.cost.toFixed(1)} $
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
