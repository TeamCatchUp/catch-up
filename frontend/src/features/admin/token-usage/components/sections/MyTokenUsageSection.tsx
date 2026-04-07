'use client';

/** 토큰 사용량 관리 > "나의 토큰 사용량" 탭 — 요약(총 사용량) + 차트 3개(일자별 바·누적 에어리어·질문 횟수 바) + 제한 설정 */

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';
import { startOfMonth, startOfToday } from 'date-fns';

import { DateRangePicker } from '@/shared/components/ui/date-range-picker';

import { tokenUsageQueries } from '../../queries/tokenUsage.queries';
import DailyUsageBarChart from '../charts/DailyUsageBarChart';
import TotalQuestionBarChart from '../charts/TotalQuestionBarChart';
import TotalTokenLineChart from '../charts/TotalTokenLineChart';
import TokenLimitSettings from '../settings/TokenLimitSettings';

export default function MyTokenUsageSection() {
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: startOfMonth(startOfToday()),
    to: startOfToday(),
  });

  const { data: summary } = useQuery(tokenUsageQueries.summary());
  const { data: periodCost } = useQuery(tokenUsageQueries.periodCost(dateRange?.from, dateRange?.to));
  const { data: dailyUsage } = useQuery(tokenUsageQueries.dailyUsage(dateRange?.from, dateRange?.to));
  const { data: totalTrend } = useQuery(tokenUsageQueries.totalTrend());
  const { data: questionCounts } = useQuery(tokenUsageQueries.questionCounts(dateRange?.from, dateRange?.to));

  return (
    <div className="flex flex-col gap-6">
      {/* 요약 행 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1.5">
          <span className="text-heading-small text-content-alternative">전체 사용 토큰량</span>
          <span className="text-heading-xlarge text-content-normal">
            {(summary?.total_cost ?? 0).toFixed(2)} $
          </span>
        </div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {/* 차트 3개 */}
      <div className="flex h-100 gap-4">
        {/* 메인 바차트 */}
        <div className="min-h-0 min-w-0 flex-1">
          <DailyUsageBarChart
            data={dailyUsage ?? []}
            totalCost={periodCost?.total_usd ?? 0}
            dailyAvg={periodCost?.daily_avg_usd}
          />
        </div>

        {/* 우측 소형 차트 2개 */}
        <div className="flex w-81 shrink-0 flex-col gap-4">
          <div className="min-h-0 flex-1">
            <TotalTokenLineChart data={totalTrend ?? []} />
          </div>
          <div className="min-h-0 flex-1">
            <TotalQuestionBarChart data={questionCounts ?? []} />
          </div>
        </div>
      </div>

      {/* 설정 */}
      <TokenLimitSettings />
    </div>
  );
}
