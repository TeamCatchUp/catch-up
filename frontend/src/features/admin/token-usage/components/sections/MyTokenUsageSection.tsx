'use client';

/** 토큰 사용량 관리 > "나의 토큰 사용량" 탭 — 요약(총 사용량+상태) + 차트 3개(일자별 바·누적 에어리어·질문 횟수 바) + 제한 설정 */

import { useMemo, useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';
import { isWithinInterval, parseISO } from 'date-fns';

import IconCheckCircle from '@/public/icons/icon/check_circle.svg';
import { Badge } from '@/shared/components/ui/badge';
import { DateRangePicker } from '@/shared/components/ui/date-range-picker';

import { DEFAULT_DAILY_LIMIT, STATUS_CONFIG } from '../../constants/tokenUsageConfig';
import { tokenUsageQueries } from '../../queries/tokenUsage.queries';
import DailyUsageBarChart from '../charts/DailyUsageBarChart';
import TotalQuestionBarChart from '../charts/TotalQuestionBarChart';
import TotalTokenLineChart from '../charts/TotalTokenLineChart';
import TokenLimitSettings from '../settings/TokenLimitSettings';

export default function MyTokenUsageSection() {
  const { data: summary } = useQuery(tokenUsageQueries.summary());
  const { data: dailyUsage } = useQuery(tokenUsageQueries.dailyUsage());
  const { data: totalTrend } = useQuery(tokenUsageQueries.totalTrend());
  const { data: questionCounts } = useQuery(tokenUsageQueries.questionCounts());

  // 날짜 범위 초기값: mock 데이터 첫날 ~ 마지막날
  const [dateRange, setDateRange] = useState<DateRange | undefined>(() => {
    if (!dailyUsage?.length) return undefined;
    return {
      from: parseISO(dailyUsage[0].date),
      to: parseISO(dailyUsage[dailyUsage.length - 1].date),
    };
  });

  // 날짜 범위로 필터링
  const filteredDaily = useMemo(() => {
    if (!dailyUsage) return [];
    if (!dateRange?.from) return dailyUsage;
    const from = dateRange.from;
    const to = dateRange.to ?? dateRange.from;
    return dailyUsage.filter((d) => isWithinInterval(parseISO(d.date), { start: from, end: to }));
  }, [dailyUsage, dateRange]);

  const filteredTrend = useMemo(() => {
    if (!totalTrend) return [];
    if (!dateRange?.from) return totalTrend;
    const from = dateRange.from;
    const to = dateRange.to ?? dateRange.from;
    return totalTrend.filter((d) => isWithinInterval(parseISO(d.date), { start: from, end: to }));
  }, [totalTrend, dateRange]);

  const filteredQuestions = useMemo(() => {
    if (!questionCounts) return [];
    if (!dateRange?.from) return questionCounts;
    const from = dateRange.from;
    const to = dateRange.to ?? dateRange.from;
    return questionCounts.filter((d) => isWithinInterval(parseISO(d.date), { start: from, end: to }));
  }, [questionCounts, dateRange]);

  const filteredTotalCost = useMemo(() => filteredDaily.reduce((sum, d) => sum + d.cost, 0), [filteredDaily]);

  if (!summary) return null;

  const statusConfig = STATUS_CONFIG[summary.status];

  return (
    <div className="flex flex-col gap-6">
      {/* 요약 행 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1.5">
          <span className="text-heading-small text-gray-50">전체 사용 토큰량</span>
          <div className="flex items-center gap-3">
            <span className="text-heading-xlarge text-gray-80">{filteredTotalCost.toFixed(2)} $</span>
            <Badge variant={statusConfig.variant} size="sm" className="gap-1 rounded-md2 py-0.5">
              <IconCheckCircle className="size-4" aria-hidden="true" />
              {statusConfig.label}
            </Badge>
          </div>
        </div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>

      {/* 차트 3개 */}
      <div className="flex h-100 gap-4">
        {/* 메인 바차트 */}
        <div className="min-h-0 min-w-0 flex-1">
          <DailyUsageBarChart data={filteredDaily} totalCost={filteredTotalCost} dailyLimit={DEFAULT_DAILY_LIMIT} />
        </div>

        {/* 우측 소형 차트 2개 */}
        <div className="flex w-81 shrink-0 flex-col gap-4">
          <div className="min-h-0 flex-1">
            <TotalTokenLineChart data={filteredTrend} />
          </div>
          <div className="min-h-0 flex-1">
            <TotalQuestionBarChart data={filteredQuestions} />
          </div>
        </div>
      </div>

      {/* 설정 */}
      <TokenLimitSettings />
    </div>
  );
}
