'use client';

/** 토큰 사용량 관리 > 나의 토큰 사용량 — 전체 토큰 사용량 누적 에어리어 차트 */

import { format, parseISO } from 'date-fns';
import { Area, AreaChart, XAxis, YAxis } from 'recharts';

import { type ChartConfig, ChartContainer, ChartTooltip } from '@/shared/components/ui/chart';

import type { TotalTokenUsageTrend } from '../../types/tokenUsage';
import ChartCustomTooltip from './ChartCustomTooltip';

interface TotalTokenLineChartProps {
  data: TotalTokenUsageTrend[];
}

const chartConfig = {
  cumulative_tokens: {
    label: '전체 토큰 사용량',
    color: 'var(--color-pink-40)',
  },
} satisfies ChartConfig;

export default function TotalTokenLineChart({ data }: TotalTokenLineChartProps) {
  const latestValue = data.length > 0 ? data[data.length - 1].cumulative_tokens : 0;

  return (
    <div className="border-edge-neutral flex h-full flex-col overflow-hidden rounded-xl border bg-fill-normal px-6 py-5">
      {/* 헤더 */}
      <div className="flex flex-col gap-1">
        <span className="text-heading-small text-content-alternative">전체 토큰 사용량</span>
        <span className="text-heading-large text-content-normal">{latestValue.toLocaleString()}</span>
      </div>

      {/* 차트 */}
      <ChartContainer config={chartConfig} className="mt-2 min-h-0 w-full flex-1">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <defs>
            <linearGradient id="fillPink" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-pink-40)" stopOpacity={0.2} />
              <stop offset="100%" stopColor="var(--color-pink-40)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" hide />
          <YAxis hide />
          <ChartTooltip
            cursor={false}
            content={
              <ChartCustomTooltip
                valueFormatter={(v) => v.toLocaleString()}
                dateFormatter={(label) => {
                  const d = parseISO(label);
                  return format(d, 'M월 d일');
                }}
              />
            }
          />
          <Area
            type="monotone"
            dataKey="cumulative_tokens"
            stroke="var(--color-pink-40)"
            strokeWidth={2}
            fill="url(#fillPink)"
            dot={{ r: 3, fill: '#f04588', stroke: 'white', strokeWidth: 2 }}
            activeDot={{ r: 4, fill: '#f04588', stroke: 'white', strokeWidth: 2 }}
          />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
