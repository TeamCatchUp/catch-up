'use client';

/** 토큰 사용량 관리 > 나의 토큰 사용량 — 일자별 토큰 사용량 바차트 (일일 제한선 포함) */

import { useMemo } from 'react';
import { format, parseISO } from 'date-fns';
import { Bar, BarChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from 'recharts';

import { type ChartConfig, ChartContainer, ChartTooltip } from '@/shared/components/ui/chart';

import type { DailyTokenUsage } from '../../types/tokenUsageModel';
import ChartCustomTooltip from './ChartCustomTooltip';

interface DailyUsageBarChartProps {
  data: DailyTokenUsage[];
  totalCost: number;
  dailyAvg?: number;
  title?: string;
}

const chartConfig = {
  cost: {
    label: '토큰 사용량',
    color: 'var(--color-blue-30)',
  },
} satisfies ChartConfig;

export default function DailyUsageBarChart({
  data,
  totalCost,
  dailyAvg,
  title = '일자별 토큰 사용량',
}: DailyUsageBarChartProps) {
  const ticks = useMemo(() => data.map((d) => d.date), [data]);

  return (
    <div className="border-edge-neutral bg-fill-normal flex h-full flex-col rounded-xl border px-6 py-5">
      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-heading-small text-content-alternative">{title}</span>
          <span className="text-heading-large text-content-normal">{totalCost.toFixed(2)} $</span>
        </div>
      </div>

      {/* 차트 */}
      <div className={`mt-2 min-h-0 flex-1 ${data.length > 12 ? 'thin-scrollbar overflow-x-auto' : ''}`}>
        <ChartContainer
          config={chartConfig}
          className="h-full w-full"
          style={data.length > 12 ? { minWidth: data.length * 40 } : undefined}
        >
          <BarChart data={data} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--color-neutral-3)" />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              ticks={ticks}
              padding={{ left: 10, right: 10 }}
              tickFormatter={(v: string) => {
                const d = parseISO(v);
                return `${format(d, 'M')}/${format(d, 'd')}`;
              }}
              tick={{ fontSize: 13, fontWeight: 400, fill: 'var(--color-content-neutral)' }}
              tickMargin={8}
            />
            <YAxis hide />
            {dailyAvg != null && dailyAvg > 0 && (
              <ReferenceLine y={dailyAvg} stroke="var(--color-blue-30)" strokeDasharray="5 5" strokeWidth={1} />
            )}
            <ChartTooltip
              cursor={false}
              content={
                <ChartCustomTooltip
                  valueFormatter={(v) => `${v.toFixed(2)} $`}
                  dateFormatter={(label) => {
                    const d = parseISO(label);
                    return format(d, 'M월 d일');
                  }}
                />
              }
            />
            <Bar dataKey="cost" fill="var(--color-blue-30)" radius={[4, 4, 0, 0]} maxBarSize={112} />
          </BarChart>
        </ChartContainer>
      </div>
    </div>
  );
}
