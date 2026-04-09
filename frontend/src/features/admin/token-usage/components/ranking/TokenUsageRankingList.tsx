'use client';

/** 조직 토큰 사용량 > 토큰 사용량 순위 리스트 (스크롤 가능) */

import DefaultProfile from '@/public/icons/icon/default_profile.svg';

import type { TokenUsageRankingEntry } from '../../types/tokenUsageModel';

interface TokenUsageRankingListProps {
  data: TokenUsageRankingEntry[];
}

export default function TokenUsageRankingList({ data }: TokenUsageRankingListProps) {
  return (
    <div className="flex h-full flex-col gap-1">
      {/* 헤더 */}
      <div className="bg-fill-strong shrink-0 rounded-md px-5 py-1.5">
        <span className="text-heading-small text-content-neutral">토큰 사용량 순위</span>
      </div>

      {/* 스크롤 리스트 */}
      <div className="thin-scrollbar flex-1 overflow-y-auto">
        {data.map((entry) => (
          <div
            key={entry.user_id}
            className="border-edge-neutral flex h-12.5 items-center justify-between border-b px-5 py-3"
          >
            {/* 좌측: 순위 + 프로필 + 이름 + 팀 */}
            <div className="flex items-center gap-4">
              {/* 순위 */}
              <span className="text-body-small text-content-alternative w-5 shrink-0 truncate text-center">
                {entry.rank}
              </span>

              {/* 프로필 + 이름 */}
              <div className="flex items-center gap-3">
                <DefaultProfile className="border-fill-strong text-content-assistive size-7.5 shrink-0 rounded-full border" />
                <span className="text-body-small text-content-normal w-15.5 shrink-0 truncate">{entry.user_name}</span>
              </div>

              {/* 팀 태그 */}
              <div className="flex w-21.5 shrink-0 items-center justify-center">
                <span className="bg-accent-green-neutral text-accent-green rounded-md2 text-body-xsmall truncate px-1.5 py-0.5">
                  {entry.department}
                </span>
              </div>
            </div>

            {/* 우측: 비용 */}
            <div className="text-body-small text-content-normal flex min-w-0 flex-1 items-center justify-end gap-0.5">
              <span className="max-w-20 truncate text-right">{entry.total_usd.toFixed(1)}</span>
              <span>$</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
