'use client';

/** 토큰 사용량 관리 > 나의 토큰 사용량 — 일자별 토큰 사용량 바차트 (일일 제한선 포함) */

import { useMemo } from 'react';
import { format, parseISO } from 'date-fns';
import { Bar, BarChart, CartesianGrid, ReferenceLine, XAxis, YAxis } from 'recharts';

import { type ChartConfig, ChartContainer, ChartTooltip } from '@/shared/components/ui/chart';

import type { DailyTokenUsage } from '../../types/tokenUsage';
import ChartCustomTooltip from './ChartCustomTooltip';

interface DailyUsageBarChartProps {
  data: DailyTokenUsage[];
  totalCost: number;
  dailyLimit: number;
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
  dailyLimit,
  title = '일자별 토큰 사용량',
}: DailyUsageBarChartProps) {
  const modelName = data[0]?.model_name ?? '';

  const ticks = useMemo(() => {
    if (data.length === 0) return [];
    if (data.length === 1) return [data[0].date];
    return [data[0].date, data[data.length - 1].date];
  }, [data]);

  return (
    <div className="border-edge-neutral flex h-full flex-col overflow-hidden rounded-xl border bg-fill-normal px-6 py-5">
      {/* 헤더 */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-heading-small text-content-alternative">{title}</span>
          <span className="text-heading-large text-content-normal">{totalCost.toFixed(2)} $</span>
        </div>
        {modelName && (
          <span className="text-body-xsmall rounded-md2 bg-fill-primary-normal-neutral text-content-primary px-1.5 py-0.5">{modelName}</span>
        )}
      </div>

      {/* 차트 */}
      <ChartContainer config={chartConfig} className="mt-2 min-h-0 w-full flex-1">
        <BarChart data={data} margin={{ top: 8, right: 0, bottom: 0, left: -20 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--color-neutral-3)" />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={false}
            ticks={ticks}
            tickFormatter={(v: string) => {
              const d = parseISO(v);
              return format(d, 'M월 d일');
            }}
            tick={{ fontSize: 13, fill: 'var(--color-gray-70)' }}
            tickMargin={8}
          />
          <YAxis hide />
          <ReferenceLine y={dailyLimit} stroke="var(--color-blue-30)" strokeDasharray="5 5" strokeWidth={1} />
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
          <Bar dataKey="cost" fill="var(--color-blue-30)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ChartContainer>
    </div>
  );
}
