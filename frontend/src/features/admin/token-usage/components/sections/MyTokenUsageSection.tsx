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
// TODO: TokenLimitSettings role별 분기 구현 후 복원
// import TokenLimitSettings from '../settings/TokenLimitSettings';

export default function MyTokenUsageSection() {
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: startOfMonth(startOfToday()),
    to: startOfToday(),
  });

  const hasDateRange = !!dateRange?.from;

  const { data: summary } = useQuery(tokenUsageQueries.summary());
  const { data: periodCost } = useQuery({
    ...tokenUsageQueries.periodCost(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });
  const { data: dailyUsage } = useQuery({
    ...tokenUsageQueries.dailyUsage(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });
  const { data: totalTrend } = useQuery(tokenUsageQueries.totalTrend());
  const { data: questionCounts } = useQuery({
    ...tokenUsageQueries.questionCounts(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });

  return (
    <div className="flex flex-col gap-6">
      {/* 요약 행 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1.5">
          <span className="text-heading-small text-text-normal-alternative">전체 사용 토큰량</span>
          <span className="text-heading-xlarge text-text-normal-normal">{(summary?.total_cost ?? 0).toFixed(2)} $</span>
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

      {/* TODO: role별 컴포넌트 분리 예정
       * MyTokenUsageSection을 공통 차트 영역(TokenUsageCharts)으로 분리하고
       * 페이지 레벨에서 role별 컴포넌트를 조합하는 구조로 전환:
       *   AdminTokenUsagePage → <TokenUsageCharts /> + <TokenLimitSettingsAdmin />
       *   MyTokenUsagePage   → <TokenUsageCharts /> + <TokenLimitSettingsUser />
       * - admin: 직접 input 편집하여 제한값 설정
       * - user: admin이 설정한 제한값을 읽기전용으로 표시
       * - API: admin용 설정 API / user용 조회 API 별도 필요
       */}
      {/* <TokenLimitSettings /> */}
    </div>
  );
}
