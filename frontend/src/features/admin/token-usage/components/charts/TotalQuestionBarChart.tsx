'use client';

/** 토큰 사용량 관리 > 나의 토큰 사용량 — 전체 질문 횟수 소형 바차트 */

import { useMemo } from 'react';
import { format, parseISO } from 'date-fns';
import { Bar, BarChart, Cell, XAxis, YAxis } from 'recharts';

import { type ChartConfig,ChartContainer, ChartTooltip } from '@/shared/components/ui/chart';

import type { TotalQuestionCount } from '../../types/tokenUsage';
import ChartCustomTooltip from './ChartCustomTooltip';

interface TotalQuestionBarChartProps {
  data: TotalQuestionCount[];
}

const chartConfig = {
  count: {
    label: '질문 횟수',
    color: 'var(--color-blue-30)',
  },
} satisfies ChartConfig;

export default function TotalQuestionBarChart({ data }: TotalQuestionBarChartProps) {
  const totalCount = useMemo(() => data.reduce((sum, d) => sum + d.count, 0), [data]);

  return (
    <div className="flex h-full flex-col rounded-xl border border-neutral-3 bg-white px-6 py-5">
      {/* 헤더 */}
      <div className="flex flex-col gap-1">
        <span className="text-heading-small text-gray-50">전체 질문 횟수</span>
        <span className="text-heading-large text-gray-80">{totalCount.toLocaleString()}</span>
      </div>

      {/* 차트 */}
      <ChartContainer config={chartConfig} className="mt-2 min-h-0 w-full flex-1">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <XAxis dataKey="date" hide />
          <YAxis hide />
          <ChartTooltip
            cursor={false}
            content={
              <ChartCustomTooltip
                valueFormatter={(v) => `${v}회`}
                dateFormatter={(label) => {
                  const d = parseISO(label);
                  return format(d, 'M월 d일');
                }}
              />
            }
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={16} minPointSize={2}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.count === 0 ? 'var(--color-neutral-5)' : 'var(--color-blue-30)'}
              />
            ))}
          </Bar>
        </BarChart>
      </ChartContainer>
    </div>
  );
}
