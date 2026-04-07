'use client';

/** 토큰 사용량 관리 > "조직 토큰 사용량" 탭 — SegmentedPicker(팀 전체/멤버 선택) + 차트 3개 + 순위 + 제한 설정 */

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useQuery } from '@tanstack/react-query';
import { startOfMonth, startOfToday } from 'date-fns';

import { DateRangePicker } from '@/shared/components/ui/date-range-picker';

import { tokenUsageQueries } from '../../queries/tokenUsage.queries';
import DailyUsageBarChart from '../charts/DailyUsageBarChart';
import TotalQuestionBarChart from '../charts/TotalQuestionBarChart';
import TotalTokenLineChart from '../charts/TotalTokenLineChart';
import MemberProfileCard from '../member/MemberProfileCard';
import TokenUsageRankingList from '../ranking/TokenUsageRankingList';
import TokenLimitSettings from '../settings/TokenLimitSettings';
import SegmentedPicker from '../ui/SegmentedPicker';

type ViewMode = 'team' | 'member';
const VIEW_OPTIONS = ['멤버 선택', '팀 전체'];
const VIEW_MAP: Record<string, ViewMode> = { '멤버 선택': 'member', '팀 전체': 'team' };
const VIEW_LABEL: Record<ViewMode, string> = { member: '멤버 선택', team: '팀 전체' };

export default function OrgTokenUsageSection() {
  const [viewMode, setViewMode] = useState<ViewMode>('team');
  const [selectedMemberId, setSelectedMemberId] = useState<string>('1');

  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: startOfMonth(startOfToday()),
    to: startOfToday(),
  });

  const selectedUserId = Number(selectedMemberId);
  const isMemberMode = viewMode === 'member';
  const hasDateRange = !!dateRange?.from;

  const { data: members } = useQuery(tokenUsageQueries.orgMembers());
  const { data: orgDailyUsage } = useQuery({
    ...tokenUsageQueries.orgDailyUsage(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });
  const { data: userDailyUsage } = useQuery({
    ...tokenUsageQueries.userDailyUsage(selectedUserId, dateRange?.from, dateRange?.to),
    enabled: isMemberMode && !!selectedUserId && hasDateRange,
  });
  const { data: orgQuestions } = useQuery({
    ...tokenUsageQueries.orgQuestionCounts(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });
  const { data: userQuestions } = useQuery({
    ...tokenUsageQueries.userQuestionCounts(selectedUserId, dateRange?.from, dateRange?.to),
    enabled: isMemberMode && !!selectedUserId && hasDateRange,
  });
  const { data: userPeriodCost } = useQuery({
    ...tokenUsageQueries.userPeriodCost(selectedUserId, dateRange?.from, dateRange?.to),
    enabled: isMemberMode && !!selectedUserId && hasDateRange,
  });
  const { data: orgPeriodCost } = useQuery({
    ...tokenUsageQueries.orgPeriodCost(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });
  const { data: totalTrend } = useQuery(tokenUsageQueries.orgTotalTrend());
  const { data: ranking } = useQuery({
    ...tokenUsageQueries.orgRanking(dateRange?.from, dateRange?.to),
    enabled: hasDateRange,
  });

  const dailyUsage = isMemberMode ? userDailyUsage : orgDailyUsage;
  const questionCounts = isMemberMode ? userQuestions : orgQuestions;
  const periodTotalCost = isMemberMode ? (userPeriodCost?.total_usd ?? 0) : (orgPeriodCost?.total_usd ?? 0);
  const periodDailyAvg = isMemberMode ? userPeriodCost?.daily_avg_usd : orgPeriodCost?.daily_avg_usd;

  const chartTitle = viewMode === 'team' ? '조직 전체 일자별 토큰 사용량' : '개인 일자별 토큰 사용량';

  return (
    <div className="flex flex-col gap-6">
      {/* 헤더 행 */}
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-heading-large text-content-normal">토큰 이용 대시보드</span>
          <span className="text-body-small text-content-alternative">
            조직의 토큰 이용 현황을 확인하고 관리할 수 있습니다.
          </span>
        </div>
        <DateRangePicker value={dateRange} onChange={setDateRange} />
      </div>
      <div className="-mb-3 flex flex-col gap-3">
        <div className="w-40.25">
          <SegmentedPicker
            options={VIEW_OPTIONS}
            value={VIEW_LABEL[viewMode]}
            onChange={(v) => setViewMode(VIEW_MAP[v] ?? 'team')}
          />
        </div>
        {viewMode === 'member' && members ? (
          <MemberProfileCard
            members={members}
            selectedMemberId={selectedMemberId}
            onSelectMember={setSelectedMemberId}
          />
        ) : null}
      </div>

      {/* 차트 3개 + 순위 */}
      <div className="flex h-142 gap-6">
        {/* 좌측: 차트 영역 */}
        <div className="flex w-150 shrink-0 flex-col gap-3">
          <div className="min-h-0 flex-[2.2]">
            <DailyUsageBarChart
              data={dailyUsage ?? []}
              totalCost={periodTotalCost}
              dailyAvg={periodDailyAvg}
              title={chartTitle}
            />
          </div>
          <div className="flex min-h-0 flex-1 gap-3">
            <div className="min-h-0 flex-1">
              <TotalTokenLineChart data={totalTrend ?? []} />
            </div>
            <div className="min-h-0 flex-1">
              <TotalQuestionBarChart data={questionCounts ?? []} />
            </div>
          </div>
        </div>

        {/* 우측: 순위 */}
        <div className="min-w-0 flex-1">{ranking && <TokenUsageRankingList data={ranking} />}</div>
      </div>

      {/* 설정 */}
      <TokenLimitSettings mode={viewMode === 'team' ? 'org' : 'member'} />
    </div>
  );
}
