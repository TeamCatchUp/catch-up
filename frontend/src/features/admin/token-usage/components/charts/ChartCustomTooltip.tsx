'use client';

import type { TooltipProps } from 'recharts';

/** 차트 공통 다크 툴팁 — 값(상단) + 날짜(하단) 형태. valueFormatter/dateFormatter로 각 차트별 포맷 커스텀 */
interface ChartCustomTooltipProps extends TooltipProps<number, string> {
  valueFormatter: (value: number) => string;
  dateFormatter: (label: string) => string;
}

export default function ChartCustomTooltip({
  active,
  payload,
  label,
  valueFormatter,
  dateFormatter,
}: ChartCustomTooltipProps) {
  if (!active || !payload?.length || !label) return null;

  const value = payload[0].value as number;

  return (
    <div className="bg-alpha-black-75 flex flex-col gap-1 rounded-xl px-3 py-2 shadow-[0px_0px_4px_0px_rgba(0,0,0,0.1),2px_6px_12px_0px_rgba(0,0,0,0.1)]">
      <span className="text-body-small font-medium text-white">{valueFormatter(value)}</span>
      <span className="text-label-small text-alpha-white-75">{dateFormatter(label)}</span>
    </div>
  );
}
